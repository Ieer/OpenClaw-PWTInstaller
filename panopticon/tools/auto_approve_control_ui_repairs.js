#!/usr/bin/env node

const fs = require("node:fs");
const net = require("node:net");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");
const { setTimeout: delay } = require("node:timers/promises");

const AGENTS = new Set(["personal", "nox", "metrics", "growth", "email", "writing", "health", "trades"]);
const SCOPES = new Set(["operator.read", "operator.write", "operator.admin", "operator.approvals", "operator.questions", "operator.pairing"]);

function ipv4(address) {
  const normalized = String(address || "").replace(/^::ffff:/i, "");
  if (net.isIP(normalized) !== 4) return null;
  return normalized.split(".").reduce((total, octet) => (total * 256 + Number(octet)) >>> 0, 0);
}

function parseCidr(value) {
  const [address, prefix, extra] = String(value).split("/");
  const numeric = ipv4(address);
  if (numeric === null || extra !== undefined || !/^\d+$/.test(prefix || "")) throw new Error("invalid LAN CIDR");
  const bits = Number(prefix);
  if (bits < 8 || bits > 32) throw new Error("LAN CIDR must have prefix 8..32");
  const mask = (0xffffffff << (32 - bits)) >>> 0;
  const network = (numeric & mask) >>> 0;
  const end = (network | (~mask >>> 0)) >>> 0;
  const privateRanges = [[0x0a000000, 0x0affffff], [0xac100000, 0xac1fffff], [0xc0a80000, 0xc0a8ffff]];
  if (!privateRanges.some(([start, stop]) => network >= start && end <= stop)) throw new Error("CIDR must be entirely RFC1918 LAN space");
  return { network, mask };
}

function validatePolicy(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("policy must be an object");
  const keys = new Set(["agents", "lanCidrs", "allowedScopes", "allowAdmin", "maxAgeSeconds", "maxApprovals", "expiresAt"]);
  if (Object.keys(value).some(key => !keys.has(key))) throw new Error("unknown policy field");
  if (!Array.isArray(value.agents) || !value.agents.length || value.agents.some(agent => !AGENTS.has(agent))) throw new Error("explicit known agents required");
  if (!Array.isArray(value.lanCidrs) || !value.lanCidrs.length) throw new Error("explicit LAN CIDRs required");
  if (!Array.isArray(value.allowedScopes) || !value.allowedScopes.length || value.allowedScopes.some(scope => !SCOPES.has(scope))) throw new Error("explicit known scopes required");
  if (value.allowedScopes.some(scope => ["operator.admin", "operator.approvals", "operator.pairing"].includes(scope)) && value.allowAdmin !== true) throw new Error("privileged Control UI scopes require allowAdmin=true");
  const maxAgeSeconds = value.maxAgeSeconds ?? 300;
  const maxApprovals = value.maxApprovals ?? 1;
  if (!Number.isInteger(maxAgeSeconds) || maxAgeSeconds < 1 || maxAgeSeconds > 900) throw new Error("request age must be 1..900 seconds");
  if (!Number.isInteger(maxApprovals) || maxApprovals < 1 || maxApprovals > 10) throw new Error("approval cap must be 1..10");
  const expiresAt = Date.parse(value.expiresAt);
  if (!Number.isFinite(expiresAt)) throw new Error("explicit policy expiry required");
  return { ...value, ranges: value.lanCidrs.map(parseCidr), maxAgeSeconds, maxApprovals, expiry: expiresAt };
}

function evaluate(item, paired, policy, now = Date.now()) {
  if (now >= policy.expiry) return "policy-expired";
  if (!item || !/^[a-f0-9-]{36}$/i.test(item.requestId || "") || !/^[a-f0-9]{64}$/i.test(item.deviceId || "") || typeof item.publicKey !== "string" || !item.publicKey) return "invalid-identity";
  if (item.clientId !== "openclaw-control-ui" || item.clientMode !== "webchat") return "not-control-ui";
  if (item.role !== "operator" || (item.roles !== undefined && (!Array.isArray(item.roles) || item.roles.some(role => role !== "operator")))) return "unexpected-role";
  const source = ipv4(item.remoteIp);
  if (source === null || !policy.ranges.some(range => ((source & range.mask) >>> 0) === range.network)) return "outside-lan-policy";
  if (!Number.isFinite(item.ts) || item.ts > now + 5000 || now - item.ts > policy.maxAgeSeconds * 1000) return "stale-request";
  if (!Array.isArray(item.scopes) || !item.scopes.length || item.scopes.some(scope => !policy.allowedScopes.includes(scope))) return "scope-denied";
  const existing = paired.find(device => device.deviceId === item.deviceId || device.publicKey === item.publicKey);
  if (existing) {
    if (existing.deviceId !== item.deviceId || existing.publicKey !== item.publicKey) return "identity-changed";
    const granted = existing.approvedScopes || existing.scopes || [];
    if (item.scopes.some(scope => !granted.includes(scope))) return "scope-upgrade-requires-human";
  } else if (item.isRepair) {
    return "unknown-repair-identity";
  }
  return "eligible";
}

function fingerprint(item) {
  return crypto.createHash("sha256").update(JSON.stringify([item.requestId, item.deviceId, item.publicKey,
    item.clientId, item.clientMode, item.role, item.roles, item.remoteIp, [...item.scopes].sort(), item.ts, item.isRepair])).digest("hex");
}

function cli(agent, args) {
  const output = execFileSync("docker", ["exec", "--user", "node", `openclaw-${agent}`, "openclaw", "devices", ...args, "--json"], {
    encoding: "utf8", timeout: 25000, maxBuffer: 2 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
  });
  return JSON.parse(output);
}

function run(policy, { apply = false, invoke = cli, log = console.log, now = Date.now, onAttempt = () => {} } = {}) {
  let attempts = 0;
  for (const agent of policy.agents) {
    if (now() >= policy.expiry) break;
    let first;
    try {
      first = invoke(agent, ["list"]);
      if (!Array.isArray(first.pending) || !Array.isArray(first.paired)) throw new Error("invalid pairing inventory");
    } catch {
      log(JSON.stringify({ agent, decision: "inventory-unavailable" }));
      continue;
    }
    log(JSON.stringify({ agent, decision: "inventory-checked", pending: first.pending.length, paired: first.paired.length }));
    for (const item of first.pending) {
      const decision = evaluate(item, first.paired, policy, now());
      if (decision !== "eligible") {
        log(JSON.stringify({ agent, requestId: item.requestId, decision }));
        continue;
      }
      if (attempts >= policy.maxApprovals) break;
      if (!apply) {
        log(JSON.stringify({ agent, requestId: item.requestId, decision: "would-approve", remoteIp: item.remoteIp, scopes: item.scopes }));
        continue;
      }
      let current;
      try {
        current = invoke(agent, ["list"]);
        if (!Array.isArray(current.pending) || !Array.isArray(current.paired)) throw new Error("invalid rechecked inventory");
      } catch {
        log(JSON.stringify({ agent, requestId: item.requestId, decision: "recheck-unavailable" }));
        continue;
      }
      const fresh = current.pending.find(request => request.requestId === item.requestId);
      if (!fresh || evaluate(fresh, current.paired, policy, now()) !== "eligible" || fingerprint(fresh) !== fingerprint(item)) {
        log(JSON.stringify({ agent, requestId: item.requestId, decision: "changed-before-approval" }));
        continue;
      }
      onAttempt();
      attempts += 1;
      try {
        invoke(agent, ["approve", item.requestId]);
        const confirmed = invoke(agent, ["list"]);
        const device = confirmed.paired?.find(entry => entry.deviceId === item.deviceId && entry.publicKey === item.publicKey);
        if (!device || !Array.isArray(confirmed.pending) || confirmed.pending.some(entry => entry.requestId === item.requestId)) throw new Error("approval outcome unconfirmed");
        log(JSON.stringify({ agent, requestId: item.requestId, deviceId: item.deviceId, decision: "approved", remoteIp: item.remoteIp, scopes: item.scopes }));
      } catch {
        log(JSON.stringify({ agent, requestId: item.requestId, decision: "approval-outcome-unknown", budgetConsumed: true }));
      }
    }
  }
  return attempts;
}

function openBudget(policy, filename) {
  const policyId = crypto.createHash("sha256").update(JSON.stringify([policy.agents, policy.lanCidrs,
    policy.allowedScopes, policy.allowAdmin, policy.maxAgeSeconds, policy.maxApprovals, policy.expiresAt])).digest("hex");
  let state = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, "utf8")) : { policyId, attempts: 0 };
  if (state.policyId !== policyId) state = { policyId, attempts: 0 };
  if (!Number.isInteger(state.attempts) || state.attempts < 0 || state.attempts > policy.maxApprovals) throw new Error("invalid approval budget state");
  return {
    remaining: () => policy.maxApprovals - state.attempts,
    consume: () => {
      if (state.attempts >= policy.maxApprovals) throw new Error("approval budget exhausted");
      const next = { policyId, attempts: state.attempts + 1 };
      const temporary = `${filename}.${crypto.randomUUID()}.part`;
      try {
        fs.writeFileSync(temporary, JSON.stringify(next), { mode: 0o600, flag: "wx" });
        fs.renameSync(temporary, filename);
      } finally {
        if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
      }
      state = next;
    },
  };
}

function acquireLock(filename) {
  const descriptor = fs.openSync(filename, "wx", 0o600);
  try {
    fs.writeFileSync(descriptor, JSON.stringify({ pid: process.pid }));
  } finally {
    fs.closeSync(descriptor);
  }
  return () => fs.unlinkSync(filename);
}

async function main() {
  const args = process.argv.slice(2);
  if (!args.length || args.includes("--help")) {
    console.log("Usage: node auto_approve_control_ui_repairs.js --policy FILE [--apply] [--watch]\nDefault: dry-run. Watch stops at policy expiry or approval cap. No token is printed or passed as a command argument.");
    return;
  }
  if (args.some(arg => !["--apply", "--policy", "--watch"].includes(arg) && arg !== args[args.indexOf("--policy") + 1])) throw new Error("unknown arguments");
  const index = args.indexOf("--policy");
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith("--")) throw new Error("policy file required");
  const policy = validatePolicy(JSON.parse(fs.readFileSync(args[index + 1], "utf8")));
  const apply = args.includes("--apply");
  const releaseLock = apply ? acquireLock(`${args[index + 1]}.lock`) : () => {};
  try {
    const budget = openBudget(policy, `${args[index + 1]}.state.json`);
    let remaining = budget.remaining();
    console.log(JSON.stringify({ decision: "monitor-started", mode: apply ? "apply" : "dry-run", agents: policy.agents,
      lanCidrs: policy.lanCidrs, expiresAt: policy.expiresAt, remaining }));
    const stop = new AbortController();
    process.once("SIGTERM", () => stop.abort());
    process.once("SIGINT", () => stop.abort());
    do {
      if (stop.signal.aborted || Date.now() >= policy.expiry) break;
      run({ ...policy, maxApprovals: remaining }, { apply, onAttempt: () => budget.consume() });
      remaining = budget.remaining();
      console.log(JSON.stringify({ decision: "scan-complete", remaining, expiresAt: policy.expiresAt }));
      if (!args.includes("--watch") || remaining <= 0 || Date.now() >= policy.expiry || stop.signal.aborted) break;
      try {
        await delay(Math.min(10000, policy.expiry - Date.now()), undefined, { signal: stop.signal });
      } catch {
        break;
      }
    } while (!stop.signal.aborted);
    console.log(JSON.stringify({ decision: "monitor-stopped", reason: stop.signal.aborted ? "signal" :
      Date.now() >= policy.expiry ? "policy-expired" : remaining <= 0 ? "approval-cap" : "single-scan", remaining }));
  } finally {
    releaseLock();
  }
}

module.exports = { parseCidr, validatePolicy, evaluate, fingerprint, run, openBudget, acquireLock };
if (require.main === module) {
  main().catch(() => {
    console.error("Automatic pairing failed; inspect policy and native device inventory. No credentials or raw CLI errors are logged.");
    process.exitCode = 1;
  });
}

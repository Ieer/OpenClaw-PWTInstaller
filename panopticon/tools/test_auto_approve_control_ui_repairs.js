const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { validatePolicy, evaluate, run, openBudget, acquireLock } = require("./auto_approve_control_ui_repairs.js");

const now = Date.now();
const policy = () => validatePolicy({ agents: ["personal"], lanCidrs: ["192.168.1.0/24"],
  allowedScopes: ["operator.read", "operator.write"], maxAgeSeconds: 300, maxApprovals: 1,
  expiresAt: new Date(now + 600000).toISOString() });
const request = () => ({ requestId: "41c42a0a-0a19-49c4-9e49-669785751b9e", deviceId: "a".repeat(64),
  publicKey: "test-public-key", clientId: "openclaw-control-ui", clientMode: "webchat", role: "operator",
  roles: ["operator"], remoteIp: "192.168.1.3", scopes: ["operator.read", "operator.write"], ts: now, isRepair: false });

test("only fresh Control UI requests in explicit private LAN qualify", () => {
  assert.equal(evaluate(request(), [], policy(), now), "eligible");
  for (const remoteIp of ["8.8.8.8", "127.0.0.1", "172.21.0.1", "192.168.1.3, 8.8.8.8", "::1"]) {
    assert.equal(evaluate({ ...request(), remoteIp }, [], policy(), now), "outside-lan-policy");
  }
  assert.equal(evaluate({ ...request(), remoteIp: "::ffff:192.168.1.3" }, [], policy(), now), "eligible");
  assert.equal(evaluate({ ...request(), scopes: ["operator.admin"] }, [], policy(), now), "scope-denied");
  assert.equal(evaluate({ ...request(), ts: now - 301000 }, [], policy(), now), "stale-request");
  assert.equal(evaluate(request(), [], policy(), now + 700000), "policy-expired");
});

test("repair flag cannot inherit identity or elevate scopes", () => {
  assert.equal(evaluate({ ...request(), isRepair: true }, [], policy(), now), "unknown-repair-identity");
  const paired = [{ ...request(), scopes: ["operator.read"] }];
  assert.equal(evaluate({ ...request(), isRepair: true }, paired, policy(), now), "scope-upgrade-requires-human");
  assert.equal(evaluate(request(), [{ ...request(), publicKey: "changed" }], policy(), now), "identity-changed");
});

test("broad, public and privileged policies fail closed", () => {
  for (const cidr of ["0.0.0.0/0", "8.8.8.0/24", "192.0.0.0/8", "172.0.0.0/8"]) {
    assert.throws(() => validatePolicy({ agents: ["personal"], lanCidrs: [cidr], allowedScopes: ["operator.read"],
      expiresAt: new Date(now + 10000).toISOString() }));
  }
  assert.throws(() => validatePolicy({ agents: ["personal"], lanCidrs: ["192.168.1.3/32"],
    allowedScopes: ["operator.admin"], expiresAt: new Date(now + 10000).toISOString() }));
});

test("privileged native Control UI needs explicitly accepted management scopes", () => {
  const elevated = validatePolicy({ agents: ["personal"], lanCidrs: ["192.168.1.3/32"],
    allowedScopes: [...request().scopes, "operator.admin", "operator.approvals", "operator.questions", "operator.pairing"],
    allowAdmin: true, expiresAt: new Date(now + 10000).toISOString() });
  assert.equal(evaluate({ ...request(), scopes: elevated.allowedScopes }, [], elevated, now), "eligible");
  assert.equal(evaluate({ ...request(), remoteIp: "192.168.1.4" }, [], elevated, now), "outside-lan-policy");
});

test("dry-run never approves and never scans other agents", () => {
  const calls = [];
  run(policy(), { invoke: (agent, args) => { calls.push([agent, args]); return { pending: [request()], paired: [] }; },
    now: () => now, log: () => {} });
  assert.deepEqual(calls, [["personal", ["list"]]]);
});

test("changed scopes on recheck prevent approval", () => {
  const calls = [];
  run(policy(), { apply: true, invoke: (agent, args) => {
    calls.push(args);
    return { pending: [{ ...request(), scopes: calls.length === 1 ? request().scopes : ["operator.admin"] }], paired: [] };
  }, now: () => now, log: () => {} });
  assert.deepEqual(calls, [["list"], ["list"]]);
});

test("eligible LAN request is rechecked, approved once and verified", () => {
  const calls = [];
  const count = run(policy(), { apply: true, invoke: (agent, args) => {
    calls.push(args);
    return calls.length < 4 ? { pending: [request()], paired: [] } : { pending: [], paired: [request()] };
  }, now: () => now, log: () => {} });
  assert.equal(count, 1);
  assert.deepEqual(calls, [["list"], ["list"], ["approve", request().requestId], ["list"]]);
});

test("all eight configured agents are evaluated with separate pairing inventories", () => {
  const agents = ["personal", "nox", "metrics", "growth", "email", "writing", "health", "trades"];
  const allPolicy = validatePolicy({ agents, lanCidrs: ["192.168.1.3/32"],
    allowedScopes: request().scopes, maxApprovals: 8, expiresAt: new Date(now + 600000).toISOString() });
  const approved = new Set();
  const calls = [];
  const count = run(allPolicy, { apply: true, invoke: (agent, args) => {
    calls.push([agent, args[0]]);
    if (args[0] === "approve") approved.add(agent);
    return approved.has(agent) ? { pending: [], paired: [request()] } : { pending: [request()], paired: [] };
  }, now: () => now, log: () => {} });
  assert.equal(count, 8);
  assert.deepEqual([...approved], agents);
  for (const agent of agents) {
    assert.deepEqual(calls.filter(([target]) => target === agent).map(([, method]) => method),
      ["list", "list", "approve", "list"]);
  }
});

test("approval cap stays global across agents", () => {
  const limited = validatePolicy({ agents: ["personal", "health", "trades"], lanCidrs: ["192.168.1.3/32"],
    allowedScopes: request().scopes, maxApprovals: 1, expiresAt: new Date(now + 600000).toISOString() });
  const approved = new Set();
  assert.equal(run(limited, { apply: true, invoke: (agent, args) => {
    if (args[0] === "approve") approved.add(agent);
    return approved.has(agent) ? { pending: [], paired: [request()] } : { pending: [request()], paired: [] };
  }, now: () => now, log: () => {} }), 1);
  assert.deepEqual([...approved], ["personal"]);
});

test("one unavailable agent does not stop other inventories", () => {
  const calls = [];
  const logs = [];
  run({ ...policy(), agents: ["health", "personal"] }, { invoke: (agent) => {
    calls.push(agent);
    if (agent === "health") throw new Error("sensitive CLI error must not be logged");
    return { pending: [], paired: [] };
  }, now: () => now, log: line => logs.push(JSON.parse(line)) });
  assert.deepEqual(calls, ["health", "personal"]);
  assert.equal(logs[0].decision, "inventory-unavailable");
  assert.equal(logs[1].decision, "inventory-checked");
  assert.equal(JSON.stringify(logs).includes("sensitive"), false);
});

test("ambiguous approval consumes budget without crashing monitor", () => {
  let consumed = 0;
  const logs = [];
  assert.equal(run(policy(), { apply: true, invoke: (agent, args) => {
    if (args[0] === "approve") throw new Error("transport disconnected");
    return { pending: [request()], paired: [] };
  }, onAttempt: () => consumed++, now: () => now, log: line => logs.push(JSON.parse(line)) }), 1);
  assert.equal(consumed, 1);
  assert.equal(logs.at(-1).decision, "approval-outcome-unknown");
});

test("approval budget survives restart and rejects overspending", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "pairing-budget-"));
  try {
    const filename = path.join(directory, "state.json");
    const first = openBudget(policy(), filename);
    first.consume();
    const restarted = openBudget(policy(), filename);
    assert.equal(restarted.remaining(), 0);
    assert.throws(() => restarted.consume());
    assert.equal(fs.statSync(filename).mode & 0o777, 0o600);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("only one applying monitor can hold a policy lock", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "pairing-lock-"));
  try {
    const filename = path.join(directory, "monitor.lock");
    const release = acquireLock(filename);
    assert.throws(() => acquireLock(filename));
    release();
    acquireLock(filename)();
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
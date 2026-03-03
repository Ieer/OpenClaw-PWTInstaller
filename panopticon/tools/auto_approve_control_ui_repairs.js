#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const AGENT_HOMES_DIR = path.join(ROOT, "agent-homes");
const DEFAULT_GATEWAY_URL = process.env.MC_GATEWAY_URL || "ws://localhost:18920";

const TARGET_CLIENT_ID = "openclaw-control-ui";
const TARGET_CLIENT_MODE = "webchat";
const APPROVE_NEW_CONTROL_UI = process.env.APPROVE_NEW_CONTROL_UI === "1";

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function listAgentSlugs() {
  const names = fs.readdirSync(AGENT_HOMES_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  return names;
}

function loadGlobalTrustedControlUiIdentities() {
  const deviceIds = new Set();
  const publicKeys = new Set();

  for (const slug of listAgentSlugs()) {
    const pairedPath = path.join(AGENT_HOMES_DIR, slug, "devices", "paired.json");
    if (!fs.existsSync(pairedPath)) {
      continue;
    }
    let paired;
    try {
      paired = loadJson(pairedPath);
    } catch {
      continue;
    }

    for (const item of Object.values(paired || {})) {
      if (!item || item.clientId !== TARGET_CLIENT_ID || item.clientMode !== TARGET_CLIENT_MODE) {
        continue;
      }
      if (item.deviceId) {
        deviceIds.add(item.deviceId);
      }
      if (item.publicKey) {
        publicKeys.add(item.publicKey);
      }
    }
  }

  return { deviceIds, publicKeys };
}

function getAgentConfig(slug) {
  const cfgPath = path.join(AGENT_HOMES_DIR, slug, "openclaw.json");
  if (!fs.existsSync(cfgPath)) {
    return null;
  }
  const cfg = loadJson(cfgPath);
  const token = String(cfg?.gateway?.auth?.token || "").trim();
  return token ? { cfgPath, token } : null;
}

function wsUrlForAgent(slug) {
  const base = DEFAULT_GATEWAY_URL.replace(/\/$/, "");
  return `${base}/chat/${slug}/`;
}

function connectAndList(slug, token) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrlForAgent(slug), {
      headers: { Origin: "http://localhost:18920" },
    });

    const connectId = `connect-${slug}-${Date.now()}`;
    let resolved = false;

    const finish = (result, isError = false) => {
      if (resolved) {
        return;
      }
      resolved = true;
      try {
        ws.close();
      } catch {
      }
      if (isError) {
        reject(result);
      } else {
        resolve(result);
      }
    };

    const timeout = setTimeout(() => {
      finish(new Error(`timeout: ${slug}`), true);
    }, 15000);

    const requests = new Map();
    const sendReq = (method, params) => {
      const id = `${method}-${slug}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
      requests.set(id, method);
      ws.send(JSON.stringify({ type: "req", id, method, params }));
      return id;
    };

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: "req",
        id: connectId,
        method: "connect",
        params: {
          minProtocol: 3,
          maxProtocol: 3,
          client: {
            id: "gateway-client",
            version: "auto-approve-script",
            platform: "linux",
            mode: "backend",
          },
          role: "operator",
          scopes: ["operator.admin", "operator.pairing"],
          auth: { token },
        },
      }));
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(String(event.data));
      } catch {
        return;
      }

      if (msg.type === "event" && msg.event === "connect.challenge") {
        return;
      }

      if (msg.type === "res" && msg.id === connectId) {
        if (!msg.ok) {
          clearTimeout(timeout);
          finish(new Error(`connect failed (${slug}): ${msg.error?.message || "unknown"}`), true);
          return;
        }
        sendReq("device.pair.list", {});
        return;
      }

      if (msg.type === "res" && requests.has(msg.id)) {
        const method = requests.get(msg.id);
        requests.delete(msg.id);

        if (!msg.ok) {
          clearTimeout(timeout);
          finish(new Error(`${method} failed (${slug}): ${msg.error?.message || "unknown"}`), true);
          return;
        }

        if (method === "device.pair.list") {
          clearTimeout(timeout);
          finish({ slug, pending: msg.payload?.pending || [], paired: msg.payload?.paired || [], sendReq }, false);
        }
      }
    };

    ws.onerror = () => {};
  });
}

async function approveForAgent(slug, token, globalTrusted) {
  const first = await connectAndList(slug, token);
  const paired = Array.isArray(first.paired) ? first.paired : [];
  const pending = Array.isArray(first.pending) ? first.pending : [];

  const knownDeviceIds = new Set(
    paired
      .filter((item) => item?.clientId === TARGET_CLIENT_ID && item?.clientMode === TARGET_CLIENT_MODE)
      .map((item) => item.deviceId)
      .filter(Boolean)
  );
  const knownPublicKeys = new Set(
    paired
      .filter((item) => item?.clientId === TARGET_CLIENT_ID && item?.clientMode === TARGET_CLIENT_MODE)
      .map((item) => item.publicKey)
      .filter(Boolean)
  );

  const candidates = pending.filter((item) => {
    if (item?.clientId !== TARGET_CLIENT_ID || item?.clientMode !== TARGET_CLIENT_MODE) {
      return false;
    }

    const matchesKnownLocal =
      (item.deviceId && knownDeviceIds.has(item.deviceId)) ||
      (item.publicKey && knownPublicKeys.has(item.publicKey));

    const matchesKnownGlobal =
      (item.deviceId && globalTrusted.deviceIds.has(item.deviceId)) ||
      (item.publicKey && globalTrusted.publicKeys.has(item.publicKey));

    const isNewControlUiCandidate =
      APPROVE_NEW_CONTROL_UI && item.clientId === TARGET_CLIENT_ID && item.clientMode === TARGET_CLIENT_MODE;

    return Boolean(item.isRepair) || matchesKnownLocal || matchesKnownGlobal || isNewControlUiCandidate;
  });

  if (candidates.length === 0) {
    return {
      slug,
      approved: 0,
      pending: pending.length,
      message: "no matching repair requests",
    };
  }

  const ws = new WebSocket(wsUrlForAgent(slug), {
    headers: { Origin: "http://localhost:18920" },
  });

  return await new Promise((resolve, reject) => {
    const connectId = `connect-approve-${slug}-${Date.now()}`;
    const requests = new Map();
    let approved = 0;
    let queue = [...candidates];

    const timeout = setTimeout(() => {
      try {
        ws.close();
      } catch {
      }
      reject(new Error(`approve timeout: ${slug}`));
    }, 20000);

    const sendReq = (method, params) => {
      const id = `${method}-${slug}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
      requests.set(id, method);
      ws.send(JSON.stringify({ type: "req", id, method, params }));
      return id;
    };

    const approveNext = () => {
      if (queue.length === 0) {
        clearTimeout(timeout);
        try {
          ws.close();
        } catch {
        }
        resolve({
          slug,
          approved,
          pending: pending.length,
          message: "approved matching repair requests",
        });
        return;
      }
      const req = queue.shift();
      sendReq("device.pair.approve", { requestId: req.requestId || req.id });
    };

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: "req",
        id: connectId,
        method: "connect",
        params: {
          minProtocol: 3,
          maxProtocol: 3,
          client: {
            id: "gateway-client",
            version: "auto-approve-script",
            platform: "linux",
            mode: "backend",
          },
          role: "operator",
          scopes: ["operator.admin", "operator.pairing"],
          auth: { token },
        },
      }));
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(String(event.data));
      } catch {
        return;
      }

      if (msg.type === "event" && msg.event === "connect.challenge") {
        return;
      }

      if (msg.type === "res" && msg.id === connectId) {
        if (!msg.ok) {
          clearTimeout(timeout);
          reject(new Error(`connect failed (${slug}): ${msg.error?.message || "unknown"}`));
          return;
        }
        approveNext();
        return;
      }

      if (msg.type === "res" && requests.has(msg.id)) {
        const method = requests.get(msg.id);
        requests.delete(msg.id);

        if (!msg.ok) {
          clearTimeout(timeout);
          reject(new Error(`${method} failed (${slug}): ${msg.error?.message || "unknown"}`));
          return;
        }

        if (method === "device.pair.approve") {
          approved += 1;
          approveNext();
        }
      }
    };

    ws.onerror = () => {};
  });
}

async function main() {
  const slugs = listAgentSlugs();
  const globalTrusted = loadGlobalTrustedControlUiIdentities();
  let failed = 0;

  for (const slug of slugs) {
    const cfg = getAgentConfig(slug);
    if (!cfg) {
      console.log(`[SKIP] ${slug} missing token/config`);
      continue;
    }

    try {
      let result;
      let lastError = null;
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
          result = await approveForAgent(slug, cfg.token, globalTrusted);
          lastError = null;
          break;
        } catch (error) {
          lastError = error;
          await new Promise((r) => setTimeout(r, 1000 * attempt));
        }
      }

      if (lastError) {
        throw lastError;
      }

      console.log(`[OK] ${slug} approved=${result.approved} pending=${result.pending} (${result.message})`);
    } catch (error) {
      failed += 1;
      console.log(`[FAIL] ${slug} ${String(error.message || error)}`);
    }
  }

  if (failed > 0) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(`[FATAL] ${String(error.message || error)}`);
  process.exit(1);
});

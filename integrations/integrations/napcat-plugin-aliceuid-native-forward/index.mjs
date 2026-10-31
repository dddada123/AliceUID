const DEADLINE_MS = 8000;
const IMAGE_LIMIT = 12 * 1024 * 1024;
let installed;

function isAliceUIDCard(payload) {
  if (payload?.message_type !== 'group' || !/^\d+$/.test(String(payload.group_id ?? ''))) return false;
  const nodes = payload.message;
  if (!Array.isArray(nodes) || nodes.length !== 2 || nodes.some(node => node?.type !== 'node')) return false;
  const header = nodes[0].data?.content;
  const picture = nodes[1].data?.content;
  if (!Array.isArray(header) || header.length !== 1 || header[0]?.type !== 'text') return false;
  if (!Array.isArray(picture) || picture.length !== 1 || picture[0]?.type !== 'image') return false;
  const title = String(header[0].data?.text ?? '').split('\n')[0];
  const recognized = title === 'AliceUID帮助' ||
    /^AliceUID·.{1,100}(?:·图鉴展示|-出刀统计)$/.test(title);
  const file = picture[0].data?.file;
  return recognized && typeof file === 'string' && file.length <= IMAGE_LIMIT &&
    /^base64:\/\/[A-Za-z0-9+/]+={0,2}$/.test(file);
}

async function limited(operation, deadline) {
  const remaining = Math.floor(deadline - performance.now());
  if (remaining <= 0) throw new Error('native deadline expired');
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(() => operation(remaining)),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('native deadline expired')), remaining); }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function stageAndForward(action, destination, nodes, logger) {
  const deadline = performance.now() + DEADLINE_MS;
  const self = String(action.core.selfInfo?.uid ?? '');
  if (!self) throw new Error('native self identity unavailable');
  const localAPI = action.obContext?.apis?.MsgApi;
  const coreAPI = action.core?.apis?.MsgApi;
  if (typeof localAPI?.createSendElements !== 'function' ||
      typeof localAPI?.sendMsgWithOb11UniqueId !== 'function' ||
      typeof coreAPI?.multiForwardMsg !== 'function') throw new Error('native API unavailable');
  const ids = [];
  let phase = 'prepare';
  try {
    for (const node of nodes) {
      phase = 'cache';
      const prepared = await limited(() => localAPI.createSendElements(node.data.content, destination), deadline);
      if (!Array.isArray(prepared?.sendElements) || prepared.sendElements.length !== node.data.content.length)
        throw new Error('native preparation incomplete');
      logger.info('[AliceUID Native] stage=cache_ready elements=' + prepared.sendElements.length);
      phase = 'self_stage';
      const message = await limited(timeout => localAPI.sendMsgWithOb11UniqueId(
        { chatType: 1, peerUid: self }, prepared.sendElements, prepared.deleteAfterSentFiles ?? [], timeout), deadline);
      if (!message?.msgId || !/^\d+$/.test(String(message.msgId))) throw new Error('native stage unconfirmed');
      ids.push(String(message.msgId));
      logger.info('[AliceUID Native] stage=self_confirmed nodes=' + ids.length);
    }
    if (ids.length !== nodes.length) throw new Error('native nodes incomplete');
    phase = 'merge';
    const message = await limited(() => coreAPI.multiForwardMsg(
      { chatType: 1, peerUid: self }, destination, ids), deadline);
    if (!message?.msgId) throw new Error('native merge unconfirmed');
    logger.info('[AliceUID Native] stage=merge_confirmed nodes=' + ids.length);
    return { message };
  } catch {
    logger.warn('[AliceUID Native] stage=' + phase + ' outcome=unconfirmed; no Packet retry');
    throw new Error('AliceUID native forward unconfirmed at ' + phase);
  }
}

export function plugin_init(ctx) {
  if (installed) return;
  const action = ctx.actions?.get?.('send_msg');
  if (typeof action?.base_handle !== 'function' ||
      typeof action?.handleForwardedNodesPacket !== 'function' ||
      typeof action?.handleForwardedNodes !== 'function') {
    ctx.logger.warn('[AliceUID Native] incompatible send_msg API; plugin inactive');
    return;
  }
  const original = action.base_handle;
  const state = { action, original, enabled: true, busy: false };
  async function wrapped(payload, ...args) {
    if (!state.enabled || !isAliceUIDCard(payload)) return original.call(this, payload, ...args);
    if (state.busy) throw new Error('AliceUID native forward busy');
    state.busy = true;
    try {
      const receiver = Object.create(this);
      const native = (peer, nodes) => stageAndForward(this, peer, nodes, ctx.logger);
      Object.defineProperties(receiver, {
        handleForwardedNodesPacket: { value: native },
        handleForwardedNodes: { value: native },
      });
      ctx.logger.info('[AliceUID Native] route=native_cached; global Packet unchanged');
      return await original.call(receiver, payload, ...args);
    } finally {
      state.busy = false;
    }
  }
  state.wrapped = wrapped;
  action.base_handle = wrapped;
  installed = state;
  ctx.logger.info('[AliceUID Native] enabled for AliceUID card forwards only');
}

export function plugin_cleanup() {
  if (!installed) return;
  installed.enabled = false;
  if (installed.action.base_handle === installed.wrapped)
    installed.action.base_handle = installed.original;
  installed = undefined;
}

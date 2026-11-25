// Host provenance and branch identity decide authorship; text is never filtered.
export const CAPTURE_PAIR_REASONS = Object.freeze([
  'capture_pair_missing', 'capture_pair_ambiguous', 'capture_pair_provenance_missing',
  'capture_pair_provenance_conflict', 'capture_pair_sidechain', 'capture_pair_incomplete',
  'capture_pair_branch_missing', 'capture_pair_turn_mismatch'
]);
export function capturePairFailure(reason = 'capture_pair_missing') {
  const safeReason = CAPTURE_PAIR_REASONS.includes(reason) ? reason : 'capture_pair_missing';
  // Existing native terminal vocabulary; detailed named outcome remains public.
  return {ok:false, state:'refused', reason:'request_refused', outcome:'not_saved',
    capture_pair_reason:safeReason,
    systemMessage:`Kovya did not save this turn (${safeReason}): a complete human/assistant pair could not be verified.`};
}
export function pairError(reason) {
  return Object.assign(new Error('Kovya capture pair could not be verified.'), {code:reason});
}
function refuse(reason) { throw pairError(reason); }
function isMeta(entry) {
  return entry?.isMeta === true || entry?.isCompactSummary === true || entry?.isHarnessControl === true;
}
function entrySession(entry) { return entry?.sessionId ?? entry?.session_id; }
export function transcriptText(content) {
  if (typeof content === 'string') return content.trim() ? content : null;
  if (!Array.isArray(content)) return null;
  const parts = content.filter(block => ['text','input_text','output_text'].includes(block?.type)
    && typeof block.text === 'string').map(block => block.text);
  const joined = parts.join('\n');
  return joined.trim() ? joined : null;
}
function isClaudeAssistant(entry) {
  return entry?.type === 'assistant' && entry.message?.role === 'assistant' && !isMeta(entry);
}
function verifyIntermediateResponses(records, finalAssistant) {
  const responses = new Map();
  for (const record of records) {
    const responseId = record.message.id;
    // Older self-contained tool records need no cross-record identity proof.
    // An unidentified record gets its own group and can never borrow a call.
    const responseKey = typeof responseId === 'string' && responseId.trim() ? responseId : record;
    if (!responses.has(responseKey)) responses.set(responseKey, []);
    responses.get(responseKey).push(record);
  }
  for (const [responseId, fragments] of responses) {
    const thinkingOnly = fragments.every(record => Array.isArray(record.message.content)
      && record.message.content.length > 0
      && record.message.content.every(block => block?.type === 'thinking'));
    if (responseId === finalAssistant.message.id && thinkingOnly) continue;

    // Proof is restricted to the selected ancestry after its nearest human.
    // One API response may split narration, thinking and tool calls across
    // records in either order. A stop reason without a real call is not proof.
    const toolIds = new Set();
    let hasToolCall = false;
    for (const record of fragments) {
      if (record.message.stop_reason !== undefined && record.message.stop_reason !== null
          && record.message.stop_reason !== 'tool_use') refuse('capture_pair_turn_mismatch');
      const content = record.message.content;
      if (typeof content === 'string' && content.trim()) continue;
      if (!Array.isArray(content) || !content.length) refuse('capture_pair_turn_mismatch');
      for (const block of content) {
        if (block?.type === 'thinking') continue;
        if (['text', 'input_text', 'output_text'].includes(block?.type) && typeof block.text === 'string') continue;
        if (block?.type !== 'tool_use' || record.message.stop_reason !== 'tool_use'
            || typeof block.id !== 'string' || !block.id.trim() || toolIds.has(block.id)) {
          refuse('capture_pair_turn_mismatch');
        }
        toolIds.add(block.id);
        hasToolCall = true;
      }
    }
    if (!hasToolCall) refuse('capture_pair_turn_mismatch');
  }
}
export function claudeTranscriptExchange(entries, {session_id, assistant_entry_id} = {}) {
  if (!Array.isArray(entries)) refuse('capture_pair_missing');
  const assistants = entries.filter(isClaudeAssistant);
  if (!assistants.length) refuse('capture_pair_missing');
  const finalAssistant = assistant_entry_id
    ? assistants.find(entry => entry.uuid === assistant_entry_id) : assistants.at(-1);
  if (!finalAssistant) refuse('capture_pair_missing');
  if (finalAssistant.isSidechain !== false) refuse('capture_pair_sidechain');
  const sessionId = session_id ?? entrySession(finalAssistant);
  if (typeof sessionId !== 'string' || !sessionId || entrySession(finalAssistant) !== sessionId) {
    refuse('capture_pair_turn_mismatch');
  }
  const entriesById = new Map();
  for (const entry of entries) {
    if (typeof entry?.uuid !== 'string') continue;
    if (entriesById.has(entry.uuid)) refuse('capture_pair_ambiguous');
    entriesById.set(entry.uuid, entry);
  }
  const ancestors = new Set();
  let cursor = finalAssistant;
  while (cursor) {
    if (ancestors.has(cursor.uuid)) refuse('capture_pair_ambiguous');
    ancestors.add(cursor.uuid);
    cursor = entriesById.get(cursor.parentUuid);
  }
  if (!assistant_entry_id && assistants.some(entry => entry.isSidechain === false
      && entrySession(entry) === sessionId && !ancestors.has(entry.uuid))) {
    refuse('capture_pair_ambiguous');
  }
  const assistantText = transcriptText(finalAssistant.message.content);
  if (finalAssistant.message.stop_reason !== 'end_turn' || !assistantText) refuse('capture_pair_incomplete');
  cursor = entriesById.get(finalAssistant.parentUuid);
  const visited = new Set();
  const intermediateAssistants = [];
  while (cursor) {
    if (visited.has(cursor.uuid)) refuse('capture_pair_ambiguous');
    visited.add(cursor.uuid);
    if (entrySession(cursor) !== sessionId || cursor.isSidechain !== false) refuse('capture_pair_turn_mismatch');
    if (isMeta(cursor)) refuse('capture_pair_provenance_conflict');
    const messageRole = cursor.message?.role;
    const payloadRole = cursor.payload?.role;
    const assistantRecord = cursor.type === 'assistant' || messageRole === 'assistant' || payloadRole === 'assistant';
    const userRecord = cursor.type === 'user' || messageRole === 'user' || payloadRole === 'user';
    if (assistantRecord && !isClaudeAssistant(cursor)) refuse('capture_pair_turn_mismatch');
    if (userRecord && (cursor.type !== 'user' || messageRole !== 'user')) refuse('capture_pair_turn_mismatch');
    if ((assistantRecord || userRecord) && payloadRole !== undefined && payloadRole !== messageRole) {
      refuse('capture_pair_turn_mismatch');
    }
    if (assistantRecord) {
      intermediateAssistants.push(cursor);
    }
    if (cursor.type === 'user' && cursor.message?.role === 'user') {
      const content = cursor.message.content;
      const isToolReply = Array.isArray(content) && content.length
        && content.every(block => block?.type === 'tool_result');
      if (isToolReply) { cursor = entriesById.get(cursor.parentUuid); continue; }
      const provenance = [cursor.origin?.kind, cursor.promptSource, cursor.turnOrigin];
      if (provenance.some(value => value === undefined)) refuse('capture_pair_provenance_missing');
      if (provenance.join('|') !== 'human|typed|human') refuse('capture_pair_provenance_conflict');
      if (Array.isArray(content) && content.some(block => !['text','input_text'].includes(block?.type))) {
        refuse('capture_pair_provenance_conflict');
      }
      const userText = transcriptText(content);
      if (!userText) refuse('capture_pair_missing');
      verifyIntermediateResponses(intermediateAssistants, finalAssistant);
      return {user_text:userText, assistant_text:assistantText, assistant_id:finalAssistant.uuid};
    }
    cursor = entriesById.get(cursor.parentUuid);
  }
  refuse('capture_pair_branch_missing');
}
export function codexTranscriptExchange(entries, input) {
  const turnId = input?.turn_id, sessionId = input?.session_id;
  if (typeof turnId !== 'string' || !turnId || typeof sessionId !== 'string' || !sessionId) {
    refuse('capture_pair_turn_mismatch');
  }
  // The admitted sources define retained prompt joining, but do not establish
  // typed-human provenance for Codex transcript user records. An inner user role
  // (including response_item wrappers) cannot authorize a replacement prompt.
  // Until a trusted typed-user host contract is supplied, skip this fallback.
  refuse('capture_pair_provenance_missing');
}

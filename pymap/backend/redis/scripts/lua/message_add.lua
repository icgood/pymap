local i = nil
local i, max_uid_key = next(KEYS, i)
local i, uids_key = next(KEYS, i)
local i, seq_key = next(KEYS, i)
local i, content_key = next(KEYS, i)
local i, changes_key = next(KEYS, i)
local i, recent_key = next(KEYS, i)
local i, deleted_key = next(KEYS, i)
local i, unseen_key = next(KEYS, i)
local i, max_modseq_key = next(KEYS, i)
local i, thread_keys_key = next(KEYS, i)
local i, content_refs_key = next(KEYS, i)
local i, content_data_key = next(KEYS, i)

local msg_recent = tonumber(ARGV[1])
local msg_flags = cmsgpack.unpack(ARGV[2])
local msg_date = ARGV[3]
local msg_email_id = ARGV[4]
local msg_thread_id = ARGV[5]
local msg_thread_keys = cmsgpack.unpack(ARGV[6])
local full = ARGV[7]
local full_json = ARGV[8]
local header = ARGV[9]
local header_json = ARGV[10]

local uid = redis.call('INCR', max_uid_key)

local refs = redis.call('HINCRBY', content_refs_key, msg_email_id, 1)
if refs == 1 then
    local refreshed = redis.call('PERSIST', content_data_key)
    if refreshed == 0 then
        redis.call('HSET', content_data_key, 'full', full)
        redis.call('HSET', content_data_key, 'full-json', full_json)
        redis.call('HSET', content_data_key, 'header', header)
        redis.call('HSET', content_data_key, 'header-json', header_json)
    end
end

for i, thread_key in ipairs(msg_thread_keys) do
    local thread_key_id = redis.call('HGET', thread_keys_key, thread_key)
    if thread_key_id then
        msg_thread_id = thread_key_id
        break
    end
end
for i, thread_key in ipairs(msg_thread_keys) do
    redis.call('HSET', thread_keys_key, thread_key, msg_thread_id)
end

local msg_deleted = false
local msg_seen = false
for i, flag in ipairs(msg_flags) do
    if flag == '\\Deleted' then
        msg_deleted = true
    elseif flag == '\\Seen' then
        msg_seen = true
    end
end

local message = cmsgpack.pack({
    flags = msg_flags,
    date = msg_date,
    email_id = msg_email_id,
    thread_id = msg_thread_id,
})

redis.call('HSET', uids_key, uid, message)
redis.call('ZADD', seq_key, uid, uid)
redis.call('HSET', content_key, uid, msg_email_id)

local modseq = redis.call('INCR', max_modseq_key)
redis.call('XADD', changes_key, 'MAXLEN', '~', 1000, modseq .. '-1',
    'uid', uid,
    'type', 'fetch',
    'message', message)

if msg_recent == 1 then
    redis.call('SADD', recent_key, uid)
end
if msg_deleted then
    redis.call('SADD', deleted_key, uid)
end
if not msg_seen then
    redis.call('ZADD', unseen_key, uid, uid)
end

return {uid, msg_email_id, msg_thread_id}

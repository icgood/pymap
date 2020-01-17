local i = nil
local i, uids_key = next(KEYS, i)
local i, dest_max_uid_key = next(KEYS, i)
local i, dest_uids_key = next(KEYS, i)
local i, dest_seq_key = next(KEYS, i)
local i, dest_content_key = next(KEYS, i)
local i, dest_changes_key = next(KEYS, i)
local i, dest_recent_key = next(KEYS, i)
local i, dest_deleted_key = next(KEYS, i)
local i, dest_unseen_key = next(KEYS, i)
local i, max_modseq_key = next(KEYS, i)
local i, content_refs_key = next(KEYS, i)

local source_uid = ARGV[1]
local msg_recent = tonumber(ARGV[2])

local message_str = redis.call('HGET', uids_key, source_uid)
if not message_str then
    return redis.error_reply('message not found')
end
local message = cmsgpack.unpack(message_str)

local msg_flags = message['flags']
local msg_email_id = message['email_id']

local msg_deleted = false
local msg_seen = false
for i, flag in ipairs(msg_flags) do
    if flag == '\\Deleted' then
        msg_deleted = true
    elseif flag == '\\Seen' then
        msg_seen = true
    end
end

local dest_uid = redis.call('INCR', dest_max_uid_key)
redis.call('HSET', dest_uids_key, dest_uid, message_str)
redis.call('ZADD', dest_seq_key, dest_uid, dest_uid)
redis.call('HSET', dest_content_key, dest_uid, msg_email_id)

local modseq = redis.call('INCR', max_modseq_key)
redis.call('XADD', dest_changes_key, 'MAXLEN', '~', 1000, modseq .. '-1',
    'uid', dest_uid,
    'type', 'fetch',
    'message', message_str)

if msg_recent == 1 then
    redis.call('SADD', dest_recent_key, dest_uid)
end
if msg_deleted then
    redis.call('SADD', dest_deleted_key, dest_uid)
end
if not msg_seen then
    redis.call('ZADD', dest_unseen_key, dest_uid, dest_uid)
end

redis.call('HINCRBY', content_refs_key, msg_email_id, 1)

return {dest_uid}

local i = nil
local i, uids_key = next(KEYS, i)
local i, seq_key = next(KEYS, i)
local i, content_key = next(KEYS, i)
local i, changes_key = next(KEYS, i)
local i, recent_key = next(KEYS, i)
local i, deleted_key = next(KEYS, i)
local i, unseen_key = next(KEYS, i)
local i, dest_max_uid_key = next(KEYS, i)
local i, dest_uids_key = next(KEYS, i)
local i, dest_seq_key = next(KEYS, i)
local i, dest_content_key = next(KEYS, i)
local i, dest_changes_key = next(KEYS, i)
local i, dest_recent_key = next(KEYS, i)
local i, dest_deleted_key = next(KEYS, i)
local i, dest_unseen_key = next(KEYS, i)
local i, max_modseq_key = next(KEYS, i)

local source_uid = ARGV[1]
local msg_recent = tonumber(ARGV[2])

local message_str = redis.call('HGET', uids_key, source_uid)
if not message_str then
    return redis.error_reply('message not found')
end

local msg_email_id = redis.call('HGET', content_key, source_uid)

redis.call('HDEL', uids_key, source_uid)
redis.call('ZREM', seq_key, source_uid)
redis.call('HDEL', content_key, source_uid)
redis.call('SREM', recent_key, source_uid)
local msg_deleted = redis.call('SREM', deleted_key, source_uid)
local msg_unseen = redis.call('ZREM', unseen_key, source_uid)

redis.call('XADD', changes_key, 'MAXLEN', '~', 1000, '*',
    'uid', source_uid,
    'type', 'expunge')

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
if msg_deleted == 1 then
    redis.call('SADD', dest_deleted_key, dest_uid)
end
if msg_unseen == 1 then
    redis.call('ZADD', dest_unseen_key, dest_uid, dest_uid)
end

return {dest_uid}

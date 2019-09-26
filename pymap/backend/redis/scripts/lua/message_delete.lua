local i = nil
local i, uids_key = next(KEYS, i)
local i, seq_key = next(KEYS, i)
local i, content_key = next(KEYS, i)
local i, changes_key = next(KEYS, i)
local i, recent_key = next(KEYS, i)
local i, deleted_key = next(KEYS, i)
local i, unseen_key = next(KEYS, i)
local i, max_modseq_key = next(KEYS, i)
local i, cleanup_contents_key = next(KEYS, i)

local uids = cmsgpack.unpack(ARGV[1])
local namespace = ARGV[2]
local mailbox_id = ARGV[3]

local msg_email_ids = redis.call('HMGET', content_key, unpack(uids))

redis.call('HDEL', uids_key, unpack(uids))
redis.call('ZREM', seq_key, unpack(uids))
redis.call('HDEL', content_key, unpack(uids))
redis.call('SREM', recent_key, unpack(uids))
redis.call('SREM', deleted_key, unpack(uids))
redis.call('ZREM', unseen_key, unpack(uids))

for i, uid in ipairs(uids) do
    local modseq = redis.call('INCR', max_modseq_key)
    redis.call('XADD', changes_key, 'MAXLEN', '~', 1000, modseq .. '-1',
        'uid', uid,
        'type', 'expunge')
end

local content_cleanup_vals = {}
for i, email_id in ipairs(msg_email_ids) do
    if email_id then
        local cleanup_val = string.format('%s\0%s', namespace, email_id)
        table.insert(content_cleanup_vals, cleanup_val)
    end
end
if next(content_cleanup_vals) then
    redis.call('RPUSH', cleanup_contents_key, unpack(content_cleanup_vals))
end

return redis.status_reply('OK')

local max_mod_key = KEYS[1]
local uids_key = KEYS[2]
local mod_seq_key = KEYS[3]
local seq_key = KEYS[4]
local recent_key = KEYS[5]
local deleted_key = KEYS[6]
local unseen_key = KEYS[7]
local expunged_key = KEYS[8]
local dates_key = KEYS[9]
local email_ids_key = KEYS[10]
local thread_ids_key = KEYS[11]
local cleanup_messages_key = KEYS[12]
local cleanup_contents_key = KEYS[13]

local uids = cjson.decode(ARGV[1])
local namespace = ARGV[2]
local mailbox_id = ARGV[3]

local mod_seq = redis.call('INCR', max_mod_key)
local email_ids = redis.call('HMGET', email_ids_key, unpack(uids))

redis.call('SREM', uids_key, unpack(uids))
redis.call('ZREM', seq_key, unpack(uids))
redis.call('ZREM', mod_seq_key, unpack(uids))
redis.call('SREM', recent_key, unpack(uids))
redis.call('SREM', deleted_key, unpack(uids))
redis.call('ZREM', unseen_key, unpack(uids))
redis.call('HDEL', dates_key, unpack(uids))
redis.call('HDEL', email_ids_key, unpack(uids))
redis.call('HDEL', thread_ids_key, unpack(uids))

for i, uid in ipairs(uids) do
    redis.call('ZADD', expunged_key, mod_seq, uid)
end

local content_cleanup_vals = {}
for i, email_id in ipairs(email_ids) do
    if email_id then
        local cleanup_val = string.format('%s\0%s', namespace, email_id)
        table.insert(content_cleanup_vals, cleanup_val)
    end
end
if #content_cleanup_vals > 0 then
    redis.call('RPUSH', cleanup_contents_key, unpack(content_cleanup_vals))
end

local message_cleanup_vals = {}
for i, uid in ipairs(uids) do
    local cleanup_val = string.format('%s\0%s\0%i', namespace, mailbox_id, uid)
    table.insert(message_cleanup_vals, cleanup_val)
end
if #message_cleanup_vals > 0 then
    redis.call('RPUSH', cleanup_messages_key, unpack(message_cleanup_vals))
end

return redis.status_reply('OK')

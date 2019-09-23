local max_mod_key = KEYS[1]
local uids_key = KEYS[2]
local mod_seq_key = KEYS[3]
local seq_key = KEYS[4]
local recent_key = KEYS[5]
local deleted_key = KEYS[6]
local unseen_key = KEYS[7]
local expunged_key = KEYS[8]
local cleanup_messages_key = KEYS[9]

local uids = cjson.decode(ARGV[1])
local namespace = ARGV[2]
local mailbox_id = ARGV[3]

local mod_seq = redis.call('INCR', max_mod_key)

redis.call('SREM', uids_key, unpack(uids))
redis.call('ZREM', seq_key, unpack(uids))
redis.call('ZREM', mod_seq_key, unpack(uids))
redis.call('SREM', recent_key, unpack(uids))
redis.call('SREM', deleted_key, unpack(uids))
redis.call('ZREM', unseen_key, unpack(uids))

local cleanup_vals = {}
for i, uid in ipairs(uids) do
    redis.call('ZADD', expunged_key, mod_seq, uid)

    local cleanup_val = string.format('%s\0%s\0%i', namespace, mailbox_id, uid)
    table.insert(cleanup_vals, cleanup_val)
end

redis.call('RPUSH', cleanup_messages_key, unpack(cleanup_vals))

return redis.status_reply('OK')

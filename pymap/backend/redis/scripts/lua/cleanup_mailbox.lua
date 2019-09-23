local cleanup_messages_key = KEYS[1]
local uids_key = KEYS[2]
local remaining = 3

local ttl = ARGV[1]
local namespace = ARGV[2]
local mailbox_id = ARGV[3]

local uids = redis.call('SMEMBERS', uids_key)
for i, uid in ipairs(uids) do
    local cleanup_val = string.format('%s\0%s\0%s', namespace, mailbox_id, uid)
    redis.call('RPUSH', cleanup_messages_key, cleanup_val)
end

for i = remaining, #KEYS do
    redis.call('EXPIRE', KEYS[i], ttl)
end

return redis.status_reply('OK')

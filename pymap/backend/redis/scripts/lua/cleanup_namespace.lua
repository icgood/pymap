local cleanup_mailboxes_key = KEYS[1]
local mailboxes_key = KEYS[2]
local remaining = 3

local ttl = ARGV[1]
local namespace = ARGV[2]

local mailbox_ids = redis.call('HVALS', mailboxes_key)
for i, mbx_id in ipairs(mailbox_ids) do
    local cleanup_val = string.format('%s\0%s', namespace, mbx_id)
    redis.call('RPUSH', cleanup_mailboxes_key, cleanup_val)
end

for i = remaining, #KEYS do
    redis.call('EXPIRE', KEYS[i], ttl)
end

return redis.status_reply('OK')

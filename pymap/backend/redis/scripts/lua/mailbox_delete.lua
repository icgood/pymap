local mailboxes_key = KEYS[1]
local order_key = KEYS[2]
local cleanup_mailboxes_key = KEYS[3]

local name = ARGV[1]
local namespace = ARGV[2]

local mailbox_id = redis.call('HGET', mailboxes_key, name)

if not mailbox_id then
    return redis.error_reply('mailbox not found')
end

redis.call('HDEL', mailboxes_key, name)
redis.call('ZREM', order_key, mailbox_id)

local cleanup_val = string.format('%s\0%s', namespace, mailbox_id)
redis.call('RPUSH', cleanup_mailboxes_key, cleanup_val)

return redis.status_reply('OK')

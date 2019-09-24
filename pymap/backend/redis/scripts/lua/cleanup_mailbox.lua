local cleanup_contents_key = KEYS[1]
local content_key = KEYS[2]
local remaining = 3

local ttl = ARGV[1]
local namespace = ARGV[2]
local mailbox_id = ARGV[3]

local email_ids = redis.call('HVALS', content_key)
for i, email_id in ipairs(email_ids) do
    local cleanup_val = string.format('%s\0%s', namespace, email_id)
    redis.call('RPUSH', cleanup_contents_key, cleanup_val)
end

for i = remaining, #KEYS do
    redis.call('EXPIRE', KEYS[i], ttl)
end

return redis.status_reply('OK')

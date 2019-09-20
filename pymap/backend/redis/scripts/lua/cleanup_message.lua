local cleanup_contents_key = KEYS[1]
local immutable_key = KEYS[2]
local remaining = 3

local ttl = ARGV[1]
local namespace = ARGV[2]

local email_id = redis.call('HGET', immutable_key, 'emailid')
local cleanup_val = string.format('%s\0%s', namespace, email_id)
redis.call('RPUSH', cleanup_contents_key, cleanup_val)

for i = remaining, #KEYS do
    redis.call('EXPIRE', KEYS[i], ttl)
end

return redis.status_reply('OK')

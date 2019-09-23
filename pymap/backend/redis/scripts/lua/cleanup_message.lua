
local ttl = ARGV[1]
local namespace = ARGV[2]

for i, key in ipairs(KEYS) do
    redis.call('EXPIRE', key, ttl)
end

return redis.status_reply('OK')

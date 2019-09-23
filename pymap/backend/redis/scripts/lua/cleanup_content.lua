local data_key = KEYS[1]

local ttl = ARGV[1]
local email_id = ARGV[2]

local refs = redis.call('HINCRBY', data_key, 'refs', -1)

if refs == 0 then
    redis.call('EXPIRE', data_key, ttl)
end

return redis.status_reply('OK')

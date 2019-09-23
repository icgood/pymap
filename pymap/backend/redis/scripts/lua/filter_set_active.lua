local filter_names_key = KEYS[1]
local name = ARGV[1]
local active_name = ARGV[2]

local filter_id = redis.call('HGET', filter_names_key, name)
if filter_id then
    redis.call('HSET', filter_names_key, active_name, filter_id)
    return redis.status_reply('OK')
else
    return redis.error_reply('filter not found')
end

local filter_names_key = KEYS[1]
local before_name = ARGV[1]
local after_name = ARGV[2]

local before_id = redis.call('HGET', filter_names_key, before_name)
local after_id = redis.call('HGET', filter_names_key, after_name)
if not before_id then
    return redis.error_reply('filter not found')
elseif after_id then
    return redis.error_reply('filter already exists')
end
redis.call('HDEL', filter_names_key, before_name)
redis.call('HSET', filter_names_key, after_name, before_id)
return redis.status_reply('OK')

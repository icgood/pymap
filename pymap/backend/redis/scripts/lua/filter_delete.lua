local filter_names_key = KEYS[1]
local filter_data_key = KEYS[2]
local name = ARGV[1]
local active_name = ARGV[2]

local filter_id = redis.call('HGET', filter_names_key, name)
local active_id = redis.call('HGET', filter_names_key, active_name)
if not filter_id then
    return redis.error_reply('filter not found')
elseif filter_id == active_id then
    return redis.error_reply('filter is active')
end
redis.call('HDEL', filter_names_key, name)
redis.call('HDEL', filter_data_key, filter_id)
return redis.status_reply('OK')

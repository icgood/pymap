local filter_names_key = KEYS[1]
local filter_data_key = KEYS[2]
local name = ARGV[1]

local filter_id = redis.call('HGET', filter_names_key, name)
if filter_id then
    return redis.call('HGET', filter_data_key, filter_id)
else
    return redis.error_reply('filter not found')
end

local i = nil
local i, uids_key = next(KEYS, i)
local i, changes_key = next(KEYS, i)
local i, deleted_key = next(KEYS, i)
local i, unseen_key = next(KEYS, i)
local i, max_modseq_key = next(KEYS, i)

local uid = tonumber(ARGV[1])
local mode = ARGV[2]
local flag_set = cmsgpack.unpack(ARGV[3])

local message_str = redis.call('HGET', uids_key, uid)
if not message_str then
    return redis.error_reply('message not found')
end
local message = cmsgpack.unpack(message_str)
local msg_flags = message['flags']

local function to_map(list)
    local map = {}
    for i, v in ipairs(list) do
        map[v] = true
    end
    return map
end

local function to_list(map)
    local list = {}
    for k, v in pairs(map) do
        table.insert(list, k)
    end
    return list
end

local flag_set_map = to_map(flag_set)
local has_deleted = flag_set_map['\\Deleted']
local has_seen = flag_set_map['\\Seen']
local new_flags = nil

if mode == 'ADD' and next(flag_set) then
    local new_flags_map = {}
    for i, flag in ipairs(msg_flags) do
        new_flags_map[flag] = true
    end
    for i, flag in ipairs(flag_set) do
        new_flags_map[flag] = true
    end
    new_flags = to_list(new_flags_map)

    if has_deleted then
        redis.call('SADD', deleted_key, uid)
    end
    if has_seen then
        redis.call('ZREM', unseen_key, uid)
    end
elseif mode == 'DELETE' and next(flag_set) then
    local new_flags_map = {}
    for i, flag in ipairs(msg_flags) do
        new_flags_map[flag] = true
    end
    for i, flag in ipairs(flag_set) do
        new_flags_map[flag] = nil
    end
    new_flags = to_list(new_flags_map)

    if has_deleted then
        redis.call('SREM', deleted_key, uid)
    end
    if has_seen then
        redis.call('ZADD', unseen_key, uid, uid)
    end
elseif mode == 'REPLACE' then
    new_flags = flag_set

    if has_deleted then
        redis.call('SADD', deleted_key, uid)
    else
        redis.call('SREM', deleted_key, uid)
    end
    if has_seen then
        redis.call('ZREM', unseen_key, uid)
    else
        redis.call('ZADD', unseen_key, uid, uid)
    end
end

if new_flags then
    message['flags'] = new_flags
    message_str = cmsgpack.pack(message)

    redis.call('HSET', uids_key, uid, message_str)

    local modseq = redis.call('INCR', max_modseq_key)
    redis.call('XADD', changes_key, 'MAXLEN', '~', 1000, modseq .. '-1',
        'uid', uid,
        'type', 'fetch',
        'message', message_str)
end

return message_str

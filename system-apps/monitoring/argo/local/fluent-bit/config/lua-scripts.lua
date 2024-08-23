-- Searches for the key "template" in the log message and parses it.
-- When "{{ key }}" is found, the key inside the brackets is searched and converted to string
-- and replaces the placeholder. Tables are formatted via the cjson package.
function parse_template(tag, timestamp, record)
    local cjson = require "cjson"

    if record["template"] == nil then
        return 0, 0, {}
    end

    template_parsed = record["template"]

    for key, value in pairs(record) do
        pattern = string.format("{{ %s }}", key)

        if type(value) == "table" then
            replacement = cjson.encode(value)
        else
            replacement = value
        end

        template_parsed = template_parsed:gsub(pattern, replacement)
    end

    record["template_parsed"] = template_parsed

    return 1, timestamp, record

end

-- Extends the fluent bit kubernetes annotations: https://docs.fluentbit.io/manual/pipeline/filters/kubernetes#kubernetes-pod-annotations
-- Allows the user to specify the following annotation: "fluentbit.io/rename-log-collector: grafana"
-- This will simply rename the container.
function rename_container(tag, timestamp, record)
    if record["kubernetes"] == nil then
        return 0, 0, {}
    end

    container = record["kubernetes"]["container_name"]
    stream = record["stream"]
    annotation_name_with_stream = string.format("fluentbit.io/rename_%s-%s", stream, container)
    annotation_name = string.format("fluentbit.io/rename-%s", container)

    if record["kubernetes"]["annotations"] == nil then
        return 0, 0, {}
    end

    if record["kubernetes"]["annotations"][annotation_name_with_stream] then
        annotation_name = annotation_name_with_stream
    end

    if record["kubernetes"]["annotations"][annotation_name] == nil then
        return 0, 0, {}
    end

    record["kubernetes"]["container_name"] = record["kubernetes"]["annotations"][annotation_name]

    return 1, timestamp, record
end

-- helper function to search for a value in a table
local function has_value (tab, val)
    for index, value in ipairs(tab) do
        if value == val then
            return true
        end
    end

    return false
end

-- Using the mapping below, all level string are mapped to be standard values. Unknown ones can be added below.
function map_level(tag, timestamp, record)
    if record["level"] == nil then
        record["level"] = "unknown"
        return 1, timestamp, record
    end

    mapping = {
        critical = {"fatal", "f", "crit", "critical", "c"},
        error = {"err", "erro", "error", "e"},
        warning = {"warn", "warning", "w"},
        info = {"info", "i"},
        debug = {"dbug", "debug", "d"},
        trace = {"trace", "t"}
    }

    record["src_level"] = record["level"]

    for level, level_aliases in pairs(mapping) do
        if has_value(level_aliases, string.lower(record["level"])) then
            record["level"] = level
            return 1, timestamp, record
        end
    end

    record["level"] = "unknown"

    return 1, timestamp, record
end
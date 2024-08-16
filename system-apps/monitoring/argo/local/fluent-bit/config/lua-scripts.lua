function parse_template(tag, timestamp, record)
    local cjson = require "cjson"

    if record["template"] == nil then
        return 0, 0, {}
    end

    template_parsed = record["template"]

    new_record = record

    for key, value in pairs(record) do
        pattern = string.format("{{ %s }}", key)

        if type(value) == "table" then
            replacement = cjson.encode(value)
        else
            replacement = value
        end

        template_parsed = template_parsed:gsub(pattern, replacement)
    end

    new_record["template_parsed"] = template_parsed

    return 1, timestamp, new_record

end

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

    new_record = record
    new_record["kubernetes"]["container_name"] = record["kubernetes"]["annotations"][annotation_name]

    return 1, timestamp, new_record
end

function level_to_lower(tag, timestamp, record)
    if record["level"] == nil then
        return 0, 0, {}
    end
    record["level"] = string.lower(record["level"])
    return 1, timestamp, record
end

function map_level(tag, timestamp, record)
    if record["level"] == nil then
        return 0, 0, {}
    end

    mapping = {
        warn = "warning",
        erro = "error"
    }

    for key, value in pairs(mapping) do
        if record["level"] == key then
            new_record = record
            new_record["level"] = value
            return 1, timestamp, new_record
        end
    end

    return 0, 0, {}
end

# Update / Insert objects in a JSON list which have a primary key

def upsert(primary_key; object):
  # update or insert an object with primary_key into a list
  if isempty(select(.)) then [] else . end |
  (
    map(.[primary_key] == (object | .[primary_key])) |    # try to get the existing object for the primary key
    index(true)                                           # get the index of the object if exists
  ) as $i_obj |                                
  if $i_obj then .[$i_obj] = object else .+ [object] end; # update or insert object

def delete_elements(primary_key; value):
  # delete objects with `primary_key == value` from a list
  # value must be a string or regex
  map(select(.[primary_key] | test(value) | not ));

def append_unique(object):
  # append object to the list only if the object is not yet part of the list
  if isempty(select(.)) then [] else . end |
  (
    map(. == object) |      # try to get the index of the existing object
    index(true)
  ) as $i_obj |
  if $i_obj then . else .+ [object] end; # return the current list or append the new object

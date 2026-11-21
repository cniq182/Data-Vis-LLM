import copy

from render.spec import validate

COLUMNS = [
    "pickup", "dropoff", "passengers", "distance", "fare", "tip", "tolls",
    "total", "color", "payment", "pickup_zone", "dropoff_zone",
    "pickup_borough", "dropoff_borough",
]

count_spec = {
    "mark": "bar",
    "encoding": {
        "x": {"field": "pickup_borough", "type": "nominal", "sort": "-y"},
        "y": {"aggregate": "count"},
    },
    "config": {"view": {"width": 400, "height": 300}},
}

hour_spec = {
    "mark": "bar",
    "encoding": {
        "x": {"field": "pickup", "type": "temporal", "timeUnit": "hour"},
        "y": {"aggregate": "count"},
    },
}

variants = {}

variants["1 count, as the LLM wrote it"] = copy.deepcopy(count_spec)

no_config = copy.deepcopy(count_spec)
del no_config["config"]
variants["2 count, without config"] = no_config

with_type = copy.deepcopy(no_config)
with_type["encoding"]["y"]["type"] = "quantitative"
variants["3 count, without config, y type added"] = with_type

variants["4 hour (as the LLM wrote it)"] = copy.deepcopy(hour_spec)

hours = copy.deepcopy(hour_spec)
hours["encoding"]["x"]["timeUnit"] = "hours"
variants["5 hours (correct name)"] = hours

for name, spec in variants.items():
    try:
        validate(spec, set(COLUMNS))
        print(f"OK    {name}")
    except Exception as e:
        print(f"FAIL  {name}: {str(e)[:300]}")
# Locations API

## List cities

`GET /api/locations/cities/`

The optional `search` parameter filters city names case-insensitively.
The optional `pincode_prefix` parameter filters cities by supported pincode prefix.

Example:

`GET /api/locations/cities/?search=kol`

`GET /api/locations/cities/?pincode_prefix=700`

```json
[
  {
    "id": 1,
    "name": "Kolkata",
    "slug": "kolkata",
    "tier": 1,
    "pincode_prefixes": ["700"],
    "state": {
      "id": 1,
      "name": "West Bengal",
      "slug": "west-bengal",
      "code": "WB"
    }
  }
]
```

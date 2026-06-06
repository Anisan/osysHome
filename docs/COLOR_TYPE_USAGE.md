# Using the `color` property type

The `color` type is for RGB lamps, LED strips, Zigbee/MQTT color devices, and any integration that needs to store and convert colors between RGB, HEX, XY, HS, HSV, and related formats.

In the **Objects** module property editor, the **Color type parameters** block maps to these `params` keys:

| UI field | `params` key | Default |
|----------|--------------|---------|
| Read format | `read_format` | `canonical` |
| Write format | `write_format` | `auto` |
| Color temperature unit | `color_temp_unit` | `kelvin` |
| Hue scale | `hue_scale` | `360` |
| Saturation scale | `sat_scale` | `100` |

> For other property params (icon, history, rate_limit, …) see [PARAMS_DOCUMENTATION.md](PARAMS_DOCUMENTATION.md).

---

## Internal storage

Colors are stored internally as **universal JSON** in the database:

```json
{
  "rgb": [84, 124, 255],
  "xy": [0.192685, 0.156741],
  "Y": 23.52
}
```

- `rgb` — sRGB (0–255)
- `xy` — CIE 1931 chromaticity
- `Y` — luminance (required for correct XY ↔ RGB conversion)

Any supported input is normalized to this form on write and converted to `read_format` on read.

---

## `read_format` — read format

Controls how the property returns values via:

- `obj.getProperty("color")` / `getValue()`
- `getProperty("Object.color", data="hex")` — explicit format override
- `getHistory()` — **all** history entries use the same format
- MCP `osys_get_property`, REST history API

| `read_format` | Example output | Typical use |
|---------------|----------------|-------------|
| `canonical` | `{"rgb":[...],"xy":[...],"Y":...}` | Debugging, generic scripts |
| `hex` | `"#547CFF"` | UI, simple integrations |
| `rgb` | `{"r":84,"g":124,"b":255}` | REST/MQTT RGB |
| `xy` | `{"x":0.19,"y":0.16}` | Zigbee2MQTT XY lamps |
| `hs` | `{"hue":226,"saturation":67}` | Hue + saturation |
| `hsv` / `hsl` / `hsb` | `{"hsv":"0,90,78"}` | 3-channel color models |
| `color_temp` | kelvin or mired | White / tunable white |
| `zigbee2mqtt` | `{"color":{"x":...,"y":...}}` | Direct Z2M payloads |

**Zigbee XY lamp example:**

```json
{
  "read_format": "xy",
  "write_format": "auto",
  "hue_scale": 360,
  "sat_scale": 100,
  "color_temp_unit": "kelvin"
}
```

---

## `write_format` — write format

| Value | Behavior |
|-------|----------|
| `auto` | Detect input format automatically (recommended) |
| `hex`, `rgb`, `xy`, … | **Strict**: input must match format or `ValueError` |

`auto` accepts English color names (`red`, `warmwhite`, …), HEX, RGB strings/dicts, XY, Zigbee2MQTT `{"color":{...}}`, HSV/HSL/HSB, and canonical JSON.

---

## Color names (write by name)

With `write_format: auto`, a plain string such as `"red"` or `"relax"` is treated as a **color name** if it is listed below. Names are **English only** (case-insensitive). Localized names are not supported — use HEX, RGB, or XY instead.

```python
setProperty("Lamp.color", "red", source="Scenario")
setProperty("Lamp.color", "softwhite", source="Scenario")
setProperty("Lamp.color", "relax", source="Scenario")
```

Several names may share the same RGB (aliases). RGB values for HTML/CSS names match the [CSS named colors](https://www.w3.org/TR/css-color-4/#named-colors) / [HTML color names](https://htmlcolorcodes.com/color-names/). The authoritative map in code is `COLOR_NAME_MAP` in `app/core/lib/converters/color.py`.

### HTML / CSS (140 standard keywords)

| Group | Names |
|-------|-------|
| Red | `indianred`, `lightcoral`, `salmon`, `darksalmon`, `lightsalmon`, `crimson`, `red`, `firebrick`, `darkred` |
| Pink | `pink`, `lightpink`, `hotpink`, `deeppink`, `mediumvioletred`, `palevioletred` |
| Orange | `coral`, `tomato`, `orangered`, `darkorange`, `orange` |
| Yellow | `gold`, `yellow`, `lightyellow`, `lemonchiffon`, `lightgoldenrodyellow`, `papayawhip`, `moccasin`, `peachpuff`, `palegoldenrod`, `khaki`, `darkkhaki` |
| Purple | `lavender`, `thistle`, `plum`, `violet`, `orchid`, `fuchsia`, `magenta`, `mediumorchid`, `mediumpurple`, `rebeccapurple`, `blueviolet`, `darkviolet`, `darkorchid`, `darkmagenta`, `purple`, `indigo`, `slateblue`, `darkslateblue`, `mediumslateblue` |
| Green | `greenyellow`, `chartreuse`, `lawngreen`, `lime`, `limegreen`, `palegreen`, `lightgreen`, `mediumspringgreen`, `springgreen`, `mediumseagreen`, `seagreen`, `forestgreen`, `green`, `darkgreen`, `yellowgreen`, `olivedrab`, `olive`, `darkolivegreen`, `mediumaquamarine`, `darkseagreen`, `lightseagreen`, `darkcyan`, `teal` |
| Blue | `aqua`, `cyan`, `lightcyan`, `paleturquoise`, `aquamarine`, `turquoise`, `mediumturquoise`, `darkturquoise`, `cadetblue`, `steelblue`, `lightsteelblue`, `powderblue`, `lightblue`, `skyblue`, `lightskyblue`, `deepskyblue`, `dodgerblue`, `cornflowerblue`, `royalblue`, `blue`, `mediumblue`, `darkblue`, `navy`, `midnightblue` |
| Brown | `cornsilk`, `blanchedalmond`, `bisque`, `navajowhite`, `wheat`, `burlywood`, `tan`, `rosybrown`, `sandybrown`, `goldenrod`, `darkgoldenrod`, `peru`, `chocolate`, `saddlebrown`, `sienna`, `brown`, `maroon` |
| White | `white`, `snow`, `honeydew`, `mintcream`, `azure`, `aliceblue`, `ghostwhite`, `whitesmoke`, `seashell`, `beige`, `oldlace`, `floralwhite`, `ivory`, `antiquewhite`, `linen`, `lavenderblush`, `mistyrose` |
| Gray | `gainsboro`, `lightgray`, `lightgrey`, `silver`, `darkgray`, `darkgrey`, `gray`, `grey`, `dimgray`, `dimgrey`, `lightslategray`, `lightslategrey`, `slategray`, `slategrey`, `darkslategray`, `darkslategrey`, `black` |

Also supported (non-CSS extension): `mint`.

### Smart-home: CCT whites and scenes

RGB is computed from color temperature via `kelvin_to_rgb()` (same function used for `color_temp`).

| Name | ~K | RGB |
|------|-----|-----|
| `bedtime` | 1800 | 255, 126, 0 |
| `candlelight`, `candle`, `nightlight` | 2000 | 255, 137, 14 |
| `relax` | 2200 | 255, 146, 39 |
| `softwhite`, `incandescent` | 2700 | 255, 167, 87 |
| `neutralwhite`, `naturalwhite`, `reading` | 4000 | 255, 206, 166 |
| `brightwhite` | 5000 | 255, 228, 206 |
| `energize` | 6500 | 255, 254, 250 |
| `arcticwhite`, `coldwhite` | 7500 | 230, 235, 255 |

### Smart-home: legacy whites

Fixed RGB values kept for backward compatibility (may differ from CCT names above):

| Name | RGB |
|------|-----|
| `warmwhite` | 255, 244, 229 |
| `coolwhite` | 229, 244, 255 |
| `daylight` | 255, 255, 251 |
| `offwhite` | 253, 245, 230 |

### Smart-home: ambiance

| Name | RGB | Typical use |
|------|-----|-------------|
| `sunset` | 255, 120, 60 | Warm evening light |
| `amber` | 255, 191, 0 | Night navigation, warm accent |
| `fire` | 255, 80, 20 | Fireplace / candle effect |

> For exact Kelvin values (e.g. `2700`, `4000`) use `color_temp` format with `read_format` / `write_format` = `color_temp`, not color names.

---

## `hue_scale` and `sat_scale`

Some devices (Zigbee) use **0–254** instead of 0–360 (hue) and 0–100% (saturation). Set scales to match the device datasheet; the core normalizes on write and denormalizes on read for `hs` / `hsv` / `hsl` / `hsb`.

---

## `color_temp_unit`

Used with `read_format` / `write_format` = `color_temp`:

- `kelvin` — 2700, 4000, 6500, …
- `mired` — `1_000_000 / kelvin` (common in Zigbee)

---

## Code examples

```python
# Read (uses read_format)
color = obj.getProperty("Rgb01.color")

# Read explicit format
hex_color = obj.getProperty("Rgb01.color", "hex")

# Write
setProperty("Rgb01.color", "red", source="Scenario")
setProperty("Rgb01.color", {"color": {"x": 0.3, "y": 0.6}}, source="Zigbee")

# History (values in read_format)
history = obj.getHistory("color", limit=10, order_desc=True)
```

---

## Zigbee2MQTT payloads

### XY

```json
{"color": {"x": 0.123, "y": 0.456}}
{"color": {"r": 46, "g": 102, "b": 150}}
{"color": {"rgb": "46,102,150"}}
{"color": {"hex": "#547CFF"}}
```

### Hue / saturation

```json
{"color": {"hue": 360, "saturation": 100}}
{"color": {"hsv": "360,100,100"}}
{"color": {"h": 360, "s": 100, "v": 100}}
```

Use `read_format: xy` or `hs` / `hsv` on separate properties when one device exposes multiple color APIs.

---

## See also

- [COLOR_TYPE_USAGE.ru.md](COLOR_TYPE_USAGE.ru.md) — Russian version
- [PARAMS_DOCUMENTATION.md](PARAMS_DOCUMENTATION.md)
- [binding.md](binding.md)
- Tests: `tests/test_color_value.py`
- Color name map: `app/core/lib/converters/color.py` (`COLOR_NAME_MAP`)

// Ray traces the Snake Escape box: polished black glass with rounded edges,
// mirroring a bright photo studio, with the snakes lying still on it drawn as
// shiny raised tubes that cast little shadows. A port of the Metal shader in
// snake_escape.py, run by SwiftUI as a colour effect: one ray per pixel.
//
// The world here is view space, in points: x right, y down, z away from the
// eye, the box's middle at the origin and the eye at (0, 0, -camera). Box
// space is in half cells from the box's middle; the view rotation takes box
// space to view space. The rays use the same perspective as the Projector in
// SnakeEscapeView.swift, so the snakes SwiftUI draws on top line up.

#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

namespace snake_box {

constant float3 LIGHT = float3(-0.449, -0.799, -0.400);   // towards the light
constant float SNAKE_WIDTH = 0.25;                         // half of SE.body
constant float RIM = 1.5;                                  // half cells the edges are rounded over

struct Scene {
    float3 r0, r1, r2;                 // rows of the view rotation
    float3 box;                        // cells along x, y and z
    int side;                          // cells along a face's side in the table of cells
    float unit, camera;                // points per half cell, and from the box's middle to the eye
    device const float *cells;         // colour * 128 + the snake's shape there, for every cell
    device const float *palette;       // the snakes' colours, rgb 0-255
    float hurt;                        // 1 just after a bump, fading to 0
};

float3 to_box(Scene s, float3 v) { return v.x * s.r0 + v.y * s.r1 + v.z * s.r2; }
float3 to_view(Scene s, float3 v) { return float3(dot(s.r0, v), dot(s.r1, v), dot(s.r2, v)); }
float comp(float3 v, int i) { return i == 0 ? v.x : (i == 1 ? v.y : v.z); }
float3 unit_axis(int i) { return float3(i == 0, i == 1, i == 2); }
float3 to_linear(float3 c) { return pow(c / 255.0f, 2.2f); }

// Where a ray first goes into the box: the distance along it (-1 for a miss),
// and the axis of the face it goes in through.
float hit_box(Scene s, float3 origin, float3 dir, thread int &axis)
{
    float3 o = to_box(s, origin) / s.unit, d = to_box(s, dir) / s.unit;
    d = select(d, float3(1e-7f), fabs(d) < 1e-7f);
    float3 ta = (-s.box - o) / d, tb = (s.box - o) / d;
    float3 tn = min(ta, tb), tf = max(ta, tb);
    float near = max(max(tn.x, tn.y), tn.z), far = min(min(tf.x, tf.y), tf.z);
    if (near > far || near <= 0.0f)
        return -1.0f;
    axis = tn.x == near ? 0 : (tn.y == near ? 1 : 2);
    return near;
}

// A snake on a face, near the point (u, v) in half cells from the face's
// corner: how far the point is from the snake's middle line, which way that
// is, and the snake's colour. `arrow` says the point is on a head's arrow.
struct Body { float dist; float2 away; float3 color; bool arrow; };

Body snake_at(Scene s, int face, int a, int b, float u, float v)
{
    Body body = { 1e9f, float2(0.0f), float3(0.0f), false };
    int iu = clamp(int(u / 2.0f), 0, int(comp(s.box, a)) - 1);
    int iv = clamp(int(v / 2.0f), 0, int(comp(s.box, b)) - 1);
    int code = int(s.cells[(face * s.side + iu) * s.side + iv]);
    if (code == 0)
        return body;
    int bits = code & 127, color = code >> 7;
    body.color = float3(s.palette[3 * color], s.palette[3 * color + 1], s.palette[3 * color + 2]);
    float2 p = float2(u - (2 * iu + 1), v - (2 * iv + 1));
    const float2 ways[4] = { float2(1, 0), float2(-1, 0), float2(0, 1), float2(0, -1) };
    for (int k = 0; k < 4; k++) {
        if (!(bits & (1 << k)))
            continue;
        float2 near = ways[k] * clamp(dot(p, ways[k]), 0.0f, 1.0f);
        float d = length(p - near);
        if (d < body.dist) {
            body.dist = d;
            body.away = d > 1e-5f ? (p - near) / d : float2(0.0f);
        }
    }
    if (bits & 16) {
        float2 ahead = ways[(bits >> 5) & 3], side = float2(-ahead.y, ahead.x);
        float along = dot(p, ahead), across = dot(p, side);
        if (along > -0.16f && along < 0.66f && fabs(across) < 0.48f * (0.66f - along) / 0.82f) {
            body.arrow = true;
            body.dist = 0.0f;
            body.away = float2(0.0f);
        }
    }
    return body;
}

// A rectangular studio light seen in the direction `dir`: `centre` is the
// way to its middle, and `w` and `h` its half sizes, as tangents of angles.
float softbox(float3 dir, float3 centre, float w, float h)
{
    float facing = dot(dir, centre);
    if (facing <= 0.0f)
        return 0.0f;
    float3 across = normalize(cross(fabs(centre.y) > 0.9f ? float3(0, 0, 1) : float3(0, 1, 0), centre));
    float3 along = cross(centre, across);
    float x = fabs(dot(dir, across)) / facing, y = fabs(dot(dir, along)) / facing;
    return smoothstep(w, w * 0.8f, x) * smoothstep(h, h * 0.8f, y);
}

// The photo studio the box reflects: dark walls, a pale table underneath,
// and soft boxes overhead, behind and to the sides; just after a bump the
// whole studio flares red
float3 environment(float3 dir, float hurt)
{
    float3 color = mix(float3(0.03f), float3(0.3f), smoothstep(-0.1f, 0.9f, -dir.y));
    if (dir.y > 0.0f)
        color = mix(color, float3(0.7f), smoothstep(0.0f, 0.35f, dir.y));
    color += 9.0f * softbox(dir, float3(0.0f, -1.0f, 0.0f), 0.9f, 0.6f);
    color += 0.5f * softbox(dir, normalize(float3(0.0f, -0.45f, 0.9f)), 0.9f, 0.25f);
    color += 8.0f * softbox(dir, normalize(float3(-0.85f, -0.25f, -0.45f)), 0.14f, 0.6f);
    color += 4.0f * softbox(dir, normalize(float3(0.8f, -0.3f, 0.5f)), 0.12f, 0.55f);
    color += hurt * float3(2.5f, 0.15f, 0.1f) * (0.3f + 0.7f * smoothstep(-0.6f, 0.8f, -dir.y));
    return color;
}

float hash(float2 p) { return fract(sin(dot(p, float2(127.1f, 311.7f))) * 43758.5453f); }

// What the box looks like where a ray hits it. `pixel` is device pixels per
// point of the ray's sideways spread, to size the smoothing by.
float3 shade_box(Scene s, float3 origin, float3 dir, float t, int axis, float pixel_scale)
{
    float3 p = to_box(s, origin + t * dir) / s.unit + s.box;   // half cells from the corner
    float side = comp(p, axis) > comp(s.box, axis) ? 1.0f : -1.0f;
    int face = 2 * axis + (side > 0.0f);
    int a = axis == 0 ? 1 : 0, b = axis == 2 ? 1 : 2;
    float u = comp(p, a), v = comp(p, b);
    float3 up = unit_axis(axis) * side, ua = unit_axis(a), ub = unit_axis(b);
    float3 light = to_box(s, LIGHT);

    // Round the edges off: near one, the face turns towards the next face,
    // up to halfway at the edge itself, where the two meet
    float ea = clamp(1.0f - min(u, 2.0f * comp(s.box, a) - u) / RIM, 0.0f, 1.0f);
    float eb = clamp(1.0f - min(v, 2.0f * comp(s.box, b) - v) / RIM, 0.0f, 1.0f);
    float3 out_a = u < comp(s.box, a) ? -ua : ua, out_b = v < comp(s.box, b) ? -ub : ub;
    float3 normal = normalize(up + tan(ea * 0.785f) * out_a + tan(eb * 0.785f) * out_b);

    float3 albedo = to_linear(float3(6.0f, 6.0f, 8.0f));
    float gloss = 1.0f, base = 0.03f, shadow = 1.0f;
    float glitter = 0.0f;

    // A snake on the cell: a raised tube, or the flat arrow on its head
    Body body = snake_at(s, face, a, b, u, v);
    float width = SNAKE_WIDTH;
    float pixel = t / (s.unit * pixel_scale);   // half cells across a device pixel here
    float inside = smoothstep(width + pixel * 0.75f, width - pixel * 0.75f, body.dist);
    if (inside > 0.0f) {
        float h = clamp(body.dist / width, 0.0f, 0.95f);
        float3 tube = normalize(normal * sqrt(1.0f - h * h) + (body.away.x * ua + body.away.y * ub) * h);
        if (body.arrow)
            tube = normal;
        albedo = mix(albedo, to_linear(body.color), inside);
        normal = normalize(mix(normal, tube, inside));
        gloss = mix(gloss, 0.7f, inside);
    } else {
        if (dot(light, up) > 0.05f) {
            // The shadow of a nearby snake, which stands proud of the face
            float lift = width * 1.4f / dot(light, up);
            float su = u + dot(light, ua) * lift, sv = v + dot(light, ub) * lift;
            Body caster = snake_at(s, face, a, b, su, sv);
            shadow = 1.0f - 0.8f * smoothstep(width + 0.15f, width - 0.15f, caster.dist);
        }
        // Faint glitter in the glass
        float2 speck = floor(float2(u, v) * 7.0f) + face * 101.0f;
        if (hash(speck) > 0.997f)
            glitter = 0.08f * hash(speck + 7.0f) * (1.0f - smoothstep(0.1f, 0.3f, pixel));
    }

    // Light it, in view space
    float3 n = to_view(s, normal), eye = -normalize(dir);
    float diffuse = max(dot(n, LIGHT), 0.0f) * shadow;
    float fill = 0.3f * max(dot(n, eye), 0.0f);
    float spec = pow(max(dot(n, normalize(LIGHT + eye)), 0.0f), 90.0f) * inside;
    float fresnel = base + (1.0f - base) * pow(1.0f - max(dot(n, eye), 0.0f), 5.0f);
    float3 mirror = environment(reflect(-eye, n), s.hurt);
    float3 color = albedo * (0.1f + diffuse + fill + s.hurt * float3(0.25f, 0.0f, 0.0f));
    color += spec * 1.2f * shadow;
    color += mirror * fresnel * gloss * mix(1.0f, 0.4f + 0.6f * shadow, 1.0f - inside);
    return color + glitter;
}

}  // namespace snake_box

using namespace snake_box;

/// `frame` is the box's middle on screen (x, y), the zoom, and device pixels
/// per point; `sizes` is points per half cell, points to the eye, and the hurt
/// (0 to 1). Pixels that miss the box come out clear.
[[ stitchable ]] half4 snakeBox(float2 position, half4 color, float4 frame, float3 sizes,
                                float3 r0, float3 r1, float3 r2, float3 box,
                                device const float *cells, int cellCount,
                                device const float *palette, int paletteCount)
{
    Scene s;
    s.r0 = r0; s.r1 = r1; s.r2 = r2;
    s.box = box;
    s.side = int(max(box.x, max(box.y, box.z)));
    s.unit = sizes.x; s.camera = sizes.y; s.hurt = sizes.z;
    s.cells = cells; s.palette = palette;

    float2 at = (position - frame.xy) / frame.z;
    float3 origin = float3(0.0f, 0.0f, -s.camera);
    float3 dir = float3(at, s.camera);
    int axis;
    float t = hit_box(s, origin, dir, axis);
    if (t <= 0.0f)
        return half4(0.0h);
    float3 c = shade_box(s, origin, dir, t, axis, frame.z * frame.w);
    c = c / (1.0f + 0.25f * c);                        // soften bright highlights
    c = pow(clamp(c, 0.0f, 1.0f), 1.0f / 2.2f);
    return half4(half3(c), 1.0h);
}

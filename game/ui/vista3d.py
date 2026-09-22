"""La pista in 3D, disegnata con OpenGL dentro alla finestra di pygame.

Il resto del gioco resta com'e': pannelli, tabellone e pulsanti li disegna
pygame. La scena 3D si disegna fuori schermo, in un buffer della scheda video,
e se ne legge il risultato come un'immagine qualunque che si incolla nel
riquadro della mappa. Le macchine non sono nella scena: sono i pallini di
sempre, che chi disegna la gara mette sopra all'immagine usando `proietta`.

La ripresa e' una sola, dall'elicottero, e il lavoro sta tutto
nell'atmosfera: le ombre vere di palazzi, tribune e alberi, le nuvole che
passano e lasciano la loro ombra sui campi, la foschia in lontananza, e
un'ultima passata che sfoca i bordi come una foto di un plastico (il
"tilt-shift"), scalda i colori e scurisce gli angoli.

Se OpenGL non c'e' - la versione web, un PC senza driver, `moderngl` non
installato - `disponibile()` risponde di no e resta la mappa 2D di sempre.
"""
from __future__ import annotations

import math
import sys
from array import array

import pygame

from . import pista3d

try:
    import moderngl
except Exception:            # non installato, o nel browser
    moderngl = None

_CTX = None
_STATO = None                # None: non ancora provato


def disponibile() -> bool:
    """C'e' una scheda video con cui disegnare in 3D? Si prova una volta sola."""
    global _CTX, _STATO
    if _STATO is not None:
        return _STATO
    _STATO = False
    if moderngl is None or sys.platform == "emscripten":
        return False
    for opzioni in ({}, {"backend": "egl"}):
        try:
            _CTX = moderngl.create_standalone_context(require=330, **opzioni)
        except Exception:
            continue
        _STATO = True
        break
    return _STATO


def spegni() -> None:
    """Dopo un errore della scheda video non si riprova: si resta sul 2D."""
    global _STATO
    _STATO = False


# --------------------------------------------------------------- matrici
def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _prospettiva(fov_y: float, aspetto: float, vicino: float, lontano: float) -> list:
    f = 1.0 / math.tan(math.radians(fov_y) / 2.0)
    return [f / aspetto, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (lontano + vicino) / (vicino - lontano), -1,
            0, 0, 2 * lontano * vicino / (vicino - lontano), 0]


def _ortografica(r: float, vicino: float, lontano: float) -> list:
    return [1 / r, 0, 0, 0,
            0, 1 / r, 0, 0,
            0, 0, -2 / (lontano - vicino), 0,
            0, 0, -(lontano + vicino) / (lontano - vicino), 1]


def _guarda(occhio, bersaglio) -> list:
    f = _norm((bersaglio[0] - occhio[0], bersaglio[1] - occhio[1], bersaglio[2] - occhio[2]))
    s = _norm(_cross(f, (0.0, 1.0, 0.0)))
    u = _cross(s, f)
    return [s[0], u[0], -f[0], 0,
            s[1], u[1], -f[1], 0,
            s[2], u[2], -f[2], 0,
            -_dot(s, occhio), -_dot(u, occhio), _dot(f, occhio), 1]


def _per(a: list, b: list) -> list:
    """a * b, tutte e due per colonne come le vuole OpenGL."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _inversa(m: list) -> list:
    """Inversa di una 4x4 per colonne, con Gauss-Jordan."""
    a = [[m[c * 4 + r] for c in range(4)] + [1.0 if r == k else 0.0 for k in range(4)]
         for r in range(4)]
    for c in range(4):
        p = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        d = a[c][c] or 1e-12
        a[c] = [x / d for x in a[c]]
        for r in range(4):
            if r != c:
                k = a[r][c]
                a[r] = [x - k * y for x, y in zip(a[r], a[c])]
    return [a[r][4 + c] for c in range(4) for r in range(4)]


def _f(m) -> bytes:
    return array("f", m).tobytes()


# ---------------------------------------------------------------- shader
_VS_OMBRA = """
#version 330
uniform mat4 luce_vp;
in vec3 in_pos;
void main() { gl_Position = luce_vp * vec4(in_pos, 1.0); }
"""

_FS_OMBRA = """
#version 330
void main() {}
"""

_VS_MONDO = """
#version 330
uniform mat4 mvp;
in vec3 in_pos; in vec3 in_nor; in vec3 in_col; in float in_glow; in float in_mat; in float in_par;
in float in_aux;
out vec3 v_pos; out vec3 v_nor; out vec3 v_col; out float v_glow; flat out int v_mat; out float v_par;
out float v_aux;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_pos = in_pos; v_nor = in_nor; v_col = in_col; v_glow = in_glow;
    v_mat = int(in_mat + 0.5); v_par = in_par; v_aux = in_aux;
}
"""

# Il pittore: ogni materiale si dipinge qui, in coordinate del mondo, cosi'
# i dettagli restano fini a qualunque distanza e non costano geometria.
_FS_MONDO = """
#version 330
uniform vec3 sun; uniform vec3 sun_col; uniform vec3 amb_sky; uniform vec3 amb_ground;
uniform vec3 fog_col; uniform vec3 zenit; uniform float fog_d; uniform float fari;
uniform vec3 eye; uniform float tempo; uniform float nuvole; uniform float bagnato;
uniform vec2 origine; uniform float blocco; uniform int stile; uniform float riva;
uniform sampler2DShadow ombre; uniform mat4 luce_vp; uniform float texel;
in vec3 v_pos; in vec3 v_nor; in vec3 v_col; in float v_glow; flat in int v_mat; in float v_par;
in float v_aux;
out vec4 frag;

float h21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float rum(vec2 p) {
    vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * rum(p); p = p * 2.03 + 17.1; a *= 0.5; }
    return v;
}
// La campagna vista dal satellite: appezzamenti rettangolari, ognuno col suo
// raccolto, orientati a zone come le vecchie divisioni dei poderi, con le
// siepi e le capezzagne lungo i confini.
vec3 campi(vec2 p, vec3 prato) {
    vec2 zona = floor(p / 1100.0);
    float ang = h21(zona) * 3.14159;
    mat2 R = mat2(cos(ang), -sin(ang), sin(ang), cos(ang));
    vec2 q = R * p;
    vec2 misura = vec2(210.0, 130.0) * (0.8 + 0.4 * h21(zona + 1.3));
    vec2 cella = floor(q / misura);
    vec2 f = fract(q / misura);
    float taglio = 0.3 + 0.4 * h21(cella + 3.3);
    float parte = step(taglio, f.x);
    float id = h21(cella * 1.7 + parte * 11.0 + zona * 5.1);
    vec3 c;
    if (id < 0.34) c = prato * vec3(1.02, 1.04, 0.96);
    else if (id < 0.50) c = vec3(0.55, 0.58, 0.32);
    else if (id < 0.64) c = vec3(0.70, 0.64, 0.42);
    else if (id < 0.76) c = vec3(0.50, 0.43, 0.32);
    else if (id < 0.90) c = vec3(0.34, 0.44, 0.22);
    else c = vec3(0.62, 0.57, 0.40);
    float solchi = sin(q.y * (1.2 + id * 1.5));
    c *= 0.95 + 0.05 * solchi;
    c *= 0.88 + 0.24 * fbm(p / 70.0);
    float bx = min(min(f.x, 1.0 - f.x), abs(f.x - taglio)) * misura.x;
    float by = min(f.y, 1.0 - f.y) * misura.y;
    vec2 fz = fract(p / 1100.0);
    float bz = min(min(fz.x, 1.0 - fz.x), min(fz.y, 1.0 - fz.y)) * 1100.0;
    float bordo = min(min(bx, by), bz);
    float siepe = (1.0 - smoothstep(1.2, 3.0, bordo)) * step(0.35, rum(p / 9.0));
    c = mix(c, vec3(0.15, 0.24, 0.11), siepe * 0.85);
    c = mix(c, vec3(0.55, 0.52, 0.45), (1.0 - smoothstep(1.5, 3.5, bz)) * 0.8);
    return c;
}

vec3 albedo(out float lucido) {
    vec2 p = v_pos.xz;
    vec3 c = v_col;
    lucido = 0.0;
    if (v_mat == 1) {                           // prato e campagna
        c = v_col * (0.84 + 0.30 * fbm(p / 40.0));
        float strisce = step(0.5, fract((p.x + p.y) / 18.0));
        c *= mix(0.95 + 0.08 * strisce, 1.0, smoothstep(40.0, 90.0, v_par));
        if (stile == 2) {
            // le dune: erba bassa e sabbia che viene fuori dove il vento la scopre
            float sabbia = smoothstep(0.48, 0.66, fbm(p / 70.0));
            c = mix(c, vec3(0.80, 0.73, 0.55) * (0.9 + 0.2 * fbm(p / 9.0)), sabbia * smoothstep(30.0, 80.0, v_par));
        } else {
            float dove = stile == 1 ? 260.0 : 420.0;
            c = mix(c, campi(p, v_col), smoothstep(dove, dove + 220.0, v_par));
        }
        // il bosco visto dall'alto: chiome tonde che si toccano, con gli
        // spazi scuri fra una e l'altra
        vec2 g = p / 9.0;
        vec2 cc = floor(g) + vec2(h21(floor(g)), h21(floor(g) + 4.1)) * 0.6 + 0.2;
        float chioma = 1.0 - smoothstep(0.25, 0.75, length(fract(g) - (cc - floor(g))));
        vec3 bosco = mix(vec3(0.08, 0.15, 0.07), vec3(0.20, 0.34, 0.14) * (0.8 + 0.4 * fbm(p / 25.0)),
                         0.35 + 0.65 * chioma);
        c = mix(c, bosco, clamp(v_aux, 0.0, 1.0));
    } else if (v_mat == 2) {                    // sabbia
        float onde = sin(p.x * 0.22 + fbm(p / 30.0) * 6.0) * 0.5 + 0.5;
        c = v_col * (0.86 + 0.18 * fbm(p / 25.0) + 0.05 * onde);
        c = mix(c, vec3(0.56, 0.47, 0.34), smoothstep(0.62, 0.8, fbm(p / 300.0)) * 0.5);
    } else if (v_mat == 3) {                    // citta': strade, marciapiedi, cortili
        vec2 q = (p - origine) / blocco;
        vec2 f = abs(fract(q) - 0.5) * blocco;
        float bordo = blocco * 0.5 - max(f.x, f.y);
        vec3 cortile = v_col * (0.85 + 0.25 * fbm(p / 12.0));
        vec3 strada = vec3(0.22, 0.23, 0.25) * (0.9 + 0.2 * rum(p * 0.3));
        vec3 marcia = vec3(0.66, 0.66, 0.64);
        vec3 citta = bordo < 8.0 ? strada : (bordo < 11.0 ? marcia : cortile);
        c = mix(v_col * (0.9 + 0.2 * fbm(p / 20.0)), citta, smoothstep(35.0, 70.0, v_par));
    } else if (v_mat == 5) {                    // asfalto, con la traiettoria gommata
        c = v_col * (0.88 + 0.2 * fbm(p * 0.6));
        c *= 1.0 - 0.28 * exp(-pow(v_par * 2.4, 2.0));
        lucido = bagnato;
    } else if (v_mat == 6) {                    // tetti
        c = v_col * (0.9 + 0.14 * rum(p * 0.7));
    } else if (v_mat == 7) {                    // chiome
        c = v_col * (0.70 + 0.55 * fbm(p * 0.35));
    } else if (v_mat == 8) {                    // parcheggio, con le macchine
        vec2 g = fract(p / vec2(2.8, 13.0));
        c = v_col * (0.9 + 0.15 * rum(p * 0.5));
        if (g.x < 0.07 && g.y < 0.8) c = vec3(0.85);
        vec2 posto = floor(p / vec2(2.8, 13.0));
        float h = h21(posto);
        if (h < 0.55 && g.x > 0.2 && g.x < 0.85 && g.y > 0.15 && g.y < 0.65)
            c = mix(vec3(0.85, 0.85, 0.88), vec3(h * 1.5, 0.3 + h, 0.9 - h), step(0.25, h));
    } else if (v_mat == 9) {                    // la folla in tribuna
        vec2 k = floor(p * 2.2);
        vec3 gente = vec3(h21(k + 3.1), h21(k + 5.3), h21(k));
        c = mix(v_col, gente, 0.22) * (0.85 + 0.15 * step(0.5, fract(p.y * 0.6)));
    } else if (v_mat == 10) {                   // ghiaia
        c = v_col * (0.8 + 0.4 * h21(floor(p * 3.0)));
    } else if (v_mat == 12) {                   // strade di campagna
        c = v_col * (0.9 + 0.15 * rum(p * 0.4));
        lucido = bagnato * 0.6;
    }
    if (riva > 0.5 && (v_mat == 1 || v_mat == 2 || v_mat == 3)) {
        float spiaggia = smoothstep(-0.45, -0.8, v_pos.y);
        c = mix(c, vec3(0.84, 0.77, 0.60) * (0.9 + 0.15 * fbm(p / 6.0)), spiaggia);
    }
    return c;
}

float ombra(vec3 n) {
    vec4 ls = luce_vp * vec4(v_pos + n * 0.6, 1.0);
    vec3 q = ls.xyz / ls.w * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0 || q.z > 1.0) return 1.0;
    float s = 0.0;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++)
        s += texture(ombre, vec3(q.xy + vec2(i, j) * texel, q.z - 0.0015));
    return s / 9.0;
}

void main() {
    vec3 n = normalize(v_nor);
    vec3 vista = normalize(eye - v_pos);
    float dist = length(v_pos - eye);
    vec2 p = v_pos.xz;
    // le nuvole passano e lasciano la loro ombra sui campi
    float nube = smoothstep(0.42, 0.72, fbm(p / 900.0 + vec2(tempo * 0.010, tempo * 0.004)));
    float sole = ombra(n) * (1.0 - nube * (0.35 + 0.45 * nuvole));
    float lucido;
    vec3 c;
    if (v_mat == 11) {
        // l'acqua: scura in basso, cielo riflesso di taglio, il sole che luccica
        vec2 w = vec2(fbm(p / 7.0 + tempo * 0.08), fbm(p / 7.0 - tempo * 0.06)) - 0.5;
        vec3 nn = normalize(vec3(w.x * 0.07, 1.0, w.y * 0.07));
        float fres = pow(1.0 - max(dot(vista, nn), 0.0), 4.0);
        vec3 fondo = vec3(0.06, 0.20, 0.26) * (amb_sky + sun_col * 0.5 * sole);
        vec3 cielo = mix(fog_col, zenit, 0.4);
        c = mix(fondo, cielo, 0.15 + 0.75 * fres);
        c += sun_col * pow(max(dot(reflect(-sun, nn), vista), 0.0), 300.0) * 0.9 * sole;
        c += vec3(1.0, 0.85, 0.6) * fari * 0.06;
    } else {
        vec3 a = albedo(lucido);
        vec3 amb = mix(amb_ground, amb_sky, n.y * 0.5 + 0.5);
        float lambert = max(dot(n, sun), 0.0);
        c = a * (amb + sun_col * lambert * sole);
        if (lucido > 0.0) {
            vec3 cielo = mix(fog_col, zenit, 0.5);
            float fres = pow(1.0 - max(dot(vista, n), 0.0), 3.0);
            c = mix(c, cielo * 0.8, lucido * (0.25 + 0.5 * fres));
            c += sun_col * pow(max(dot(reflect(-sun, n), vista), 0.0), 60.0) * lucido * sole;
        }
        c += a * v_glow * fari * vec3(1.0, 0.86, 0.62);
    }
    float f = 1.0 - exp(-pow(dist / fog_d, 1.6));
    frag = vec4(mix(c, fog_col, clamp(f, 0.0, 1.0)), 1.0);
}
"""

_VS_PIENO = """
#version 330
in vec2 in_ndc;
out vec2 v_ndc; out vec2 v_uv;
void main() { v_ndc = in_ndc; v_uv = in_ndc * 0.5 + 0.5; gl_Position = vec4(in_ndc, 0.9999, 1.0); }
"""

_FS_CIELO = """
#version 330
uniform mat4 inv_vp; uniform vec3 eye; uniform vec3 zenit; uniform vec3 orizzonte;
uniform vec3 sun; uniform vec3 sun_col; uniform float stelle;
in vec2 v_ndc; in vec2 v_uv;
out vec4 frag;
float h21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
void main() {
    vec4 p = inv_vp * vec4(v_ndc, 1.0, 1.0);
    vec3 dir = normalize(p.xyz / p.w - eye);
    float h = clamp(dir.y, 0.0, 1.0);
    vec3 c = mix(orizzonte, zenit, pow(h, 0.5));
    float s = max(dot(dir, sun), 0.0);
    c += sun_col * (pow(s, 900.0) * 1.5 + pow(s, 8.0) * 0.18);
    vec2 cella = floor(dir.xz / max(dir.y, 0.05) * 90.0);
    c += vec3(0.9) * step(0.9975, h21(cella)) * stelle * h;
    frag = vec4(c, 1.0);
}
"""

# Due passate di sfocatura, in orizzontale e in verticale, a mezza risoluzione:
# servono sia al tilt-shift sia al bagliore delle luci di notte.
_FS_SFOCA = """
#version 330
uniform sampler2D tex; uniform vec2 passo;
in vec2 v_uv;
out vec4 frag;
void main() {
    float w[5] = float[](0.227, 0.194, 0.121, 0.054, 0.016);
    vec3 c = texture(tex, v_uv).rgb * w[0];
    for (int i = 1; i < 5; i++) {
        c += texture(tex, v_uv + passo * float(i)).rgb * w[i];
        c += texture(tex, v_uv - passo * float(i)).rgb * w[i];
    }
    frag = vec4(c, 1.0);
}
"""

_FS_FINALE = """
#version 330
uniform sampler2D scena; uniform sampler2D sfocata; uniform float notte; uniform float tilt;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec3 c = texture(scena, v_uv).rgb;
    vec3 b = texture(sfocata, v_uv).rgb;
    // il tilt-shift: nitido dove si guarda, sfocato in alto (lontano) e un
    // filo in basso, come la foto di un plastico. v_uv.y = 0 e' la cima
    // dell'immagine, perche' la scena e' disegnata gia' ribaltata
    float t = max(smoothstep(0.38, 0.0, v_uv.y), smoothstep(0.86, 1.0, v_uv.y) * 0.6);
    c = mix(c, b, t * tilt);
    // il bagliore delle luci forti, molto piu' vivo di notte
    c += max(b - vec3(0.72), vec3(0.0)) * (0.35 + 1.8 * notte);
    // una curva morbida sulle luci, colori un filo piu' caldi e saturi
    c = c * (1.0 + c / 6.0) / (1.0 + c * 0.55);
    float l = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(vec3(l), c, 1.12);
    c = mix(c, c * c * (3.0 - 2.0 * c), 0.25);
    c *= mix(vec3(1.0), vec3(1.03, 1.0, 0.95), 1.0 - notte);
    vec2 d = (v_uv - 0.5) * vec2(1.25, 1.0);
    c *= mix(0.78, 1.0, smoothstep(0.85, 0.25, length(d)));
    frag = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""


class Elicottero:
    """La ripresa dall'alto: gira piano da sola, finche' non la si prende.

    Si trascina col sinistro per girarla, col destro per spostarla, e la
    rotellina avvicina.
    """

    def __init__(self):
        self.yaw = math.radians(215)
        self.pitch = math.radians(57)
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.fermo = 0.0

    def aggiorna(self, dt: float) -> None:
        if self.fermo > 0:
            self.fermo -= dt
        else:
            self.yaw += dt * math.radians(0.8)

    def trascina(self, dx: float, dy: float) -> None:
        self.yaw += dx * 0.006
        self.pitch = max(math.radians(28), min(math.radians(88), self.pitch + dy * 0.004))
        self.fermo = 15.0

    def sposta(self, dx: float, dy: float, geo) -> None:
        """Il piano segue il mouse: si trascina la mappa, non la camera."""
        k = geo.span * 0.0016 * self.zoom
        fx, fz = math.cos(self.yaw), math.sin(self.yaw)
        # destra dello schermo = (-fz, fx), avanti = (fx, fz)
        self.pan[0] -= (-fz * dx - fx * dy) * k
        self.pan[1] -= (fx * dx - fz * dy) * k
        lim = geo.span * 0.6
        self.pan = [max(-lim, min(lim, v)) for v in self.pan]
        self.fermo = 15.0

    def rotella(self, y: float) -> None:
        self.zoom = max(0.2, min(1.6, self.zoom * (0.87 ** y)))
        self.fermo = 15.0

    def inquadra(self, geo, aspetto: float, fov: float) -> tuple:
        bersaglio = (geo.cx + self.pan[0], geo.cy, geo.cz + self.pan[1])
        mezzo = math.tan(math.radians(fov) / 2.0) * min(aspetto, 1.3)
        dist = geo.span * 0.66 / mezzo * self.zoom
        cp = math.cos(self.pitch)
        occhio = (bersaglio[0] - math.cos(self.yaw) * cp * dist,
                  bersaglio[1] + math.sin(self.pitch) * dist,
                  bersaglio[2] - math.sin(self.yaw) * cp * dist)
        return occhio, bersaglio, max(2.0, dist * 0.05), geo.span * 70


_GEO: dict = {}


def geometria(track) -> pista3d.Geometria:
    """La geometria di un circuito, costruita una volta sola per partita."""
    g = _GEO.get(track.id)
    if g is None:
        _GEO.clear()
        g = _GEO[track.id] = pista3d.Geometria(track)
    return g


FOV = 34.0
OMBRA_MISURA = 4096


class Vista3D:
    """Una pista caricata sulla scheda video, pronta da disegnare."""

    def __init__(self, track):
        if not disponibile():
            raise RuntimeError("OpenGL non disponibile")
        ctx = self.ctx = _CTX
        self.geo = geometria(track)
        self.p_mondo = ctx.program(vertex_shader=_VS_MONDO, fragment_shader=_FS_MONDO)
        self.p_ombra = ctx.program(vertex_shader=_VS_OMBRA, fragment_shader=_FS_OMBRA)
        self.p_cielo = ctx.program(vertex_shader=_VS_PIENO, fragment_shader=_FS_CIELO)
        self.p_sfoca = ctx.program(vertex_shader=_VS_PIENO, fragment_shader=_FS_SFOCA)
        self.p_finale = ctx.program(vertex_shader=_VS_PIENO, fragment_shader=_FS_FINALE)
        self.vbo = ctx.buffer(self.geo.vert.tobytes())
        self.vao = ctx.vertex_array(self.p_mondo, [
            (self.vbo, "3f 3f 3f 1f 1f 1f 1f", "in_pos", "in_nor", "in_col", "in_glow",
             "in_mat", "in_par", "in_aux")])
        self.vao_ombra = ctx.vertex_array(self.p_ombra, [
            (self.vbo, "3f 40x", "in_pos")])
        self.vbo_pieno = ctx.buffer(array("f", [-1, -1, 3, -1, -1, 3]).tobytes())
        self.vao_cielo = ctx.vertex_array(self.p_cielo, [(self.vbo_pieno, "2f", "in_ndc")])
        self.vao_sfoca = ctx.vertex_array(self.p_sfoca, [(self.vbo_pieno, "2f", "in_ndc")])
        self.vao_finale = ctx.vertex_array(self.p_finale, [(self.vbo_pieno, "2f", "in_ndc")])
        self.elicottero = Elicottero()
        self.buffer = {}
        self.misura = None
        self.mvp = None
        self.nuvole = 0.0
        self.bagnato = 0.0
        self.tempo = 0.0
        self._ombre()

    def rilascia(self) -> None:
        for o in list(self.buffer.values()) + [
                self.vao, self.vao_ombra, self.vbo, self.vao_cielo, self.vao_sfoca,
                self.vao_finale, self.vbo_pieno, self.p_mondo, self.p_ombra, self.p_cielo,
                self.p_sfoca, self.p_finale, self.tex_ombre, self.fbo_ombre]:
            o.release()

    # --------------------------------------------------------------- luce
    def _luce(self) -> dict:
        n = max(0.0, min(1.0, self.nuvole))
        if self.geo.notte:
            return dict(sun=_norm((-0.3, 0.8, -0.4)), sun_col=(0.08, 0.09, 0.14),
                        amb_sky=(0.07, 0.08, 0.13), amb_ground=(0.03, 0.03, 0.04),
                        zenit=(0.006, 0.010, 0.030), orizzonte=(0.05, 0.06, 0.11),
                        fari=1.0, stelle=1.0 - n)

        def mix(a, b):
            return tuple(x + (y - x) * n for x, y in zip(a, b))
        sole = 1.0 - 0.72 * n
        # un sole da pomeriggio, basso e caldo: le ombre lunghe fanno l'ora
        return dict(sun=_norm((-0.55, 0.60, -0.42)),
                    sun_col=(1.10 * sole, 0.96 * sole, 0.80 * sole),
                    amb_sky=mix((0.36, 0.42, 0.52), (0.56, 0.58, 0.62)),
                    amb_ground=mix((0.24, 0.22, 0.18), (0.30, 0.30, 0.31)),
                    zenit=mix((0.22, 0.42, 0.72), (0.44, 0.47, 0.52)),
                    orizzonte=mix((0.78, 0.80, 0.80), (0.66, 0.68, 0.71)),
                    fari=0.0, stelle=0.0)

    def _ombre(self) -> None:
        """Le ombre si calcolano una volta: il sole e la scena non si muovono."""
        geo, ctx = self.geo, self.ctx
        sole = self._luce()["sun"]
        r = geo.ext * 1.02
        centro = (geo.cx, geo.cy, geo.cz)
        occhio = tuple(c + s * r * 3 for c, s in zip(centro, sole))
        self.luce_vp = _per(_ortografica(r, r, r * 5), _guarda(occhio, centro))
        self.tex_ombre = ctx.depth_texture((OMBRA_MISURA, OMBRA_MISURA))
        self.tex_ombre.compare_func = "<="
        self.tex_ombre.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_ombre = ctx.framebuffer(depth_attachment=self.tex_ombre)
        self.fbo_ombre.use()
        self.fbo_ombre.clear(depth=1.0)
        ctx.enable(moderngl.DEPTH_TEST)
        self.p_ombra["luce_vp"].write(_f(self.luce_vp))
        self.vao_ombra.render(moderngl.TRIANGLES)

    # ------------------------------------------------------------- disegno
    def _buffer(self, misura) -> None:
        if self.misura == misura:
            return
        for o in self.buffer.values():
            o.release()
        ctx = self.ctx
        campioni = min(4, ctx.max_samples)
        mezza = (max(8, misura[0] // 2), max(8, misura[1] // 2))
        b = {}
        b["rb_ms"] = ctx.renderbuffer(misura, 4, samples=campioni, dtype="f2")
        b["db_ms"] = ctx.depth_renderbuffer(misura, samples=campioni)
        b["ms"] = ctx.framebuffer(b["rb_ms"], b["db_ms"])
        b["t_scena"] = ctx.texture(misura, 4, dtype="f2")
        b["scena"] = ctx.framebuffer(b["t_scena"])
        for k in ("a", "b"):
            b["t_" + k] = ctx.texture(mezza, 4, dtype="f2")
            b["t_" + k].repeat_x = b["t_" + k].repeat_y = False
            b[k] = ctx.framebuffer(b["t_" + k])
        b["t_fine"] = ctx.texture(misura, 3)
        b["fine"] = ctx.framebuffer(b["t_fine"])
        self.buffer = b
        self.mezza = mezza
        self.misura = misura

    def aggiorna(self, dt: float) -> None:
        self.elicottero.aggiorna(dt)
        self.tempo += dt

    def disegna(self, misura) -> pygame.Surface:
        """Un fotogramma della pista, grande `misura`, senza le macchine."""
        misura = (max(16, int(misura[0])), max(16, int(misura[1])))
        self._buffer(misura)
        geo, ctx, b = self.geo, self.ctx, self.buffer
        occhio, bersaglio, vicino, lontano = self.elicottero.inquadra(
            geo, misura[0] / misura[1], FOV)
        proj = _prospettiva(FOV, misura[0] / misura[1], vicino, lontano)
        # la y si ribalta qui: OpenGL scrive le righe dal fondo, pygame le
        # legge dall'alto, e cosi' l'immagine esce gia' dritta
        mvp = _per(proj, _guarda(occhio, bersaglio))
        for c in range(4):
            mvp[c * 4 + 1] = -mvp[c * 4 + 1]
        self.mvp = mvp
        luce = self._luce()
        fog_d = geo.span * 4.6

        b["ms"].use()
        ctx.viewport = (0, 0, misura[0], misura[1])
        ctx.clear(*luce["orizzonte"], 1.0)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        pc = self.p_cielo
        pc["inv_vp"].write(_f(_inversa(mvp)))
        pc["eye"].value = occhio
        for k in ("zenit", "orizzonte", "sun", "sun_col", "stelle"):
            pc[k].value = luce[k]
        self.vao_cielo.render(moderngl.TRIANGLES)

        ctx.enable(moderngl.DEPTH_TEST)
        pm = self.p_mondo
        pm["mvp"].write(_f(mvp))
        pm["luce_vp"].write(_f(self.luce_vp))
        pm["eye"].value = occhio
        for k in ("sun", "sun_col", "amb_sky", "amb_ground", "fari", "zenit"):
            pm[k].value = luce[k]
        pm["fog_col"].value = luce["orizzonte"]
        pm["fog_d"].value = fog_d
        pm["tempo"].value = self.tempo
        pm["nuvole"].value = max(0.0, min(1.0, self.nuvole))
        pm["bagnato"].value = max(0.0, min(1.0, self.bagnato))
        pm["origine"].value = (geo.cx, geo.cz)
        pm["blocco"].value = pista3d.BLOCCO
        pm["stile"].value = {"parco": 0, "bosco": 1, "dune": 2}.get(geo.bioma, 0)
        pm["riva"].value = 1.0 if geo.acqua else 0.0
        pm["texel"].value = 1.0 / OMBRA_MISURA
        self.tex_ombre.use(0)
        pm["ombre"].value = 0
        self.vao.render(moderngl.TRIANGLES)
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.copy_framebuffer(b["scena"], b["ms"])

        # sfocatura a mezza risoluzione, poi la passata finale
        ps = self.p_sfoca
        ctx.viewport = (0, 0, self.mezza[0], self.mezza[1])
        b["a"].use()
        b["t_scena"].use(0)
        ps["tex"].value = 0
        ps["passo"].value = (2.0 / misura[0], 0.0)
        self.vao_sfoca.render(moderngl.TRIANGLES)
        b["b"].use()
        b["t_a"].use(0)
        ps["passo"].value = (0.0, 2.0 / misura[1])
        self.vao_sfoca.render(moderngl.TRIANGLES)

        b["fine"].use()
        ctx.viewport = (0, 0, misura[0], misura[1])
        pf = self.p_finale
        b["t_scena"].use(0)
        b["t_b"].use(1)
        pf["scena"].value = 0
        pf["sfocata"].value = 1
        pf["notte"].value = 1.0 if geo.notte else 0.0
        pf["tilt"].value = 0.85
        self.vao_finale.render(moderngl.TRIANGLES)
        dati = b["fine"].read(components=3, alignment=1)
        return pygame.image.frombytes(dati, misura, "RGB")

    def proietta(self, frazione: float, laterale: float = 0.0, alto: float = 0.0):
        """Dove cade sullo schermo un punto della pista, nell'ultimo fotogramma."""
        if self.mvp is None:
            return None
        (x, y, z), _ = self.geo.sul_giro(frazione, laterale)
        y += alto
        m = self.mvp
        cx = m[0] * x + m[4] * y + m[8] * z + m[12]
        cy = m[1] * x + m[5] * y + m[9] * z + m[13]
        cw = m[3] * x + m[7] * y + m[11] * z + m[15]
        if cw <= 0.1:
            return None
        return ((cx / cw * 0.5 + 0.5) * self.misura[0], (cy / cw * 0.5 + 0.5) * self.misura[1])

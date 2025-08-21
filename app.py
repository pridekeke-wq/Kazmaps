import math, random, hashlib, os, tempfile
import gradio as gr
import cairosvg

# ---------- utilities ----------
def seeded_rng(seed_text: str):
    import hashlib, random
    h = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))

def polar_to_xy(cx, cy, r, a):
    return (cx + r*math.cos(a), cy + r*math.sin(a))

def clamp(x, lo, hi): return max(lo, min(hi, x))

MORSE = {
    'a':'.-','b':'-...','c':'-.-.','d':'-..','e':'.','f':'..-.','g':'--.','h':'....',
    'i':'..','j':'.---','k':'-.-','l':'.-..','m':'--','n':'-.','o':'---','p':'.--.',
    'q':'--.-','r':'.-.','s':'...','t':'-','u':'..-','v':'...-','w':'.--','x':'-..-',
    'y':'-.--','z':'--..','0':'-----','1':'.----','2':'..---','3':'...--','4':'....-',
    '5':'.....','6':'-....','7':'--...','8':'---..','9':'----.','&':'.-...','@':'.--.-.',
    ':':'---...', ',':'--..--','.' :'.-.-.-',"'" :'.----.','"' :'.-..-.','?':'..--..',
    '/':'-..-.','=':'-...-','+':'.-.-.','-':'-....-','(':'-.--.',')':'-.--.-','!':'-.-.--'
}
def to_morse(s: str):
    words=[]
    for word in s.lower().split():
        letters=[]
        for ch in word:
            if ch in MORSE: letters.append(MORSE[ch])
            elif ch.isalnum(): pass
        words.append(letters)
    return words

def family_from_hair_type(h):
    h=h.lower()
    if "loc" in h: return "locs"
    if any(x in h for x in ["4a","4b","4c","coil"]): return "coil"
    if any(x in h for x in ["3a","3b","3c","curl"]): return "curl"
    if any(x in h for x in ["2a","2b","2c","wave","wavy"]): return "wave"
    return "curl"

def star_count_from_density(d): return 250 + clamp(int(d),1,5)*80
def porosity_to_variance(p): return 0.25 + (clamp(int(p),1,5)-1)*0.18
def length_to_scale(L):
    L=L.lower()
    if L.startswith("short"): return 0.85
    if L.startswith("long"): return 1.00
    return 0.93
def elasticity_to_params(e):
    e=clamp(int(e),1,5)
    tight=0.15+(e-1)*0.06
    amp=30+(e-1)*12
    freq=1.0+(e-1)*0.55
    return tight, amp, freq

# ---------- SVG primitives ----------
def svg_header(w,h):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="1" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="circleClip"><circle cx="{w/2}" cy="{h/2}" r="{min(w,h)*0.43}"/></clipPath>
  </defs>
  <rect x="0" y="0" width="{w}" height="{h}" fill="#000"/>
'''
def svg_footer(): return "</svg>\n"
def svg_circle(cx,cy,r,fill="#FFF",stroke=None,sw=1,extra=""):
    s=f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}"'
    if stroke: s+=f' stroke="{stroke}" stroke-width="{sw}"'
    if extra: s+=f' {extra}'
    return s+"/>\n"
def svg_path(d, stroke="#FFF", sw=1, fill="none", dash=None, extra=""):
    s=f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" fill="{fill}"'
    if dash: s+=f' stroke-dasharray="{dash}"'
    if extra: s+=f' {extra}'
    return s+"/>\n"
def svg_text(x,y,t,size=18,anchor="middle",fill="#FFF",extra=""):
    t=(t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" {extra}>{t}</text>\n'

# ---------- drawing ----------
def background_stars(cx,cy,R,count,rnd,var):
    out=[]
    for _ in range(count):
        a=rnd.random()*2*math.pi
        r=R*math.sqrt(rnd.random())
        x,y=polar_to_xy(cx,cy,r,a)
        s=0.6+var*rnd.random()*1.7
        out.append(svg_circle(x,y,s,extra='filter="url(#glow)"'))
    return "".join(out)

def pattern_coil(cx,cy,R,rnd,tight,var,arms=3,scale=1.0):
    out=[]; dash=f"{3.2*max(0.6,var*1.1):.1f},{2.2*max(0.6,var*1.1):.1f}"
    max_theta=5*math.pi*scale
    for j in range(arms):
        phase=(2*math.pi/arms)*j + rnd.random()*0.4
        a=R*0.01*(0.8+rnd.random()*0.4); b=tight
        pts=[]; theta=0.0
        while theta<max_theta:
            r=min(R*0.9,a*math.exp(b*theta))
            x,y=polar_to_xy(cx,cy,r,theta+phase)
            pts.append((x,y)); theta+=0.03+0.01*rnd.random()
        if len(pts)>2:
            d=f"M {pts[0][0]:.2f},{pts[0][1]:.2f} "+" ".join([f"L {x:.2f},{y:.2f}" for x,y in pts[1:]])
            out.append(svg_path(d, sw=1.3, dash=dash, extra='clip-path="url(#circleClip)"'))
    return "".join(out)

def pattern_curl(cx,cy,R,rnd,amp,freq,var,loops=6):
    out=[]; dash=f"{2.6*max(0.5,var):.1f},{2.0*max(0.5,var):.1f}"
    base_r=R*0.55
    for _ in range(loops):
        start=rnd.random()*2*math.pi
        span=(math.pi/2)+rnd.random()*math.pi/2
        steps=160; pts=[]
        for i in range(steps):
            t=i/(steps-1); ang=start+t*span
            r=base_r + math.sin(ang*freq)*amp*0.4 + (rnd.random()-0.5)*8
            x,y=polar_to_xy(cx,cy,r,ang); pts.append((x,y))
        d=f"M {pts[0][0]:.2f},{pts[0][1]:.2f} "+" ".join([f"L {x:.2f},{y:.2f}" for x,y in pts[1:]])
        out.append(svg_path(d, sw=1.1, dash=dash, extra='clip-path="url(#circleClip)"'))
    return "".join(out)

def pattern_wave(cx,cy,R,rnd,amp,freq,var):
    out=[]; dash=f"{3.0*max(0.5,var*0.9):.1f},{2.4*max(0.5,var*0.9):.1f}"
    x0=cx-R*0.9; x1=cx+R*0.9; steps=480; pts=[]; phase=rnd.random()*2*math.pi
    for i in range(steps):
        t=i/(steps-1); x=x0+t*(x1-x0)
        y=cy + math.sin((t*2*math.pi*freq)+phase)*amp + (rnd.random()-0.5)*6
        pts.append((x,y))
    d=f"M {pts[0][0]:.2f},{pts[0][1]:.2f} "+" ".join([f"L {x:.2f},{y:.2f}" for x,y in pts[1:]])
    out.append(svg_path(d, sw=1.2, dash=dash, extra='clip-path="url(#circleClip)"'))
    return "".join(out)

def pattern_locs(cx,cy,R,rnd,amp,freq,var,strands=5):
    out=[]; dash=f"{3.4*max(0.4,var*0.8):.1f},{2.0*max(0.4,var*0.8):.1f}"
    offs=[(i-(strands-1)/2)*(R*0.10) for i in range(strands)]
    for off in offs:
        x0=cx-R*0.85; x1=cx+R*0.85; steps=360; pts=[]; phase=rnd.random()*2*math.pi
        for i in range(steps):
            t=i/(steps-1); x=x0+t*(x1-x0)
            y=cy + off + math.sin((t*2*math.pi*(freq*0.7))+phase)*amp*0.5 + (rnd.random()-0.5)*4
            pts.append((x,y))
        d=f"M {pts[0][0]:.2f},{pts[0][1]:.2f} "+" ".join([f"L {x:.2f},{y:.2f}" for x,y in pts[1:]])
        out.append(svg_path(d, sw=1.6, dash=dash, extra='clip-path="url(#circleClip)"'))
    return "".join(out)

def morse_ring(cx,cy,R,message):
    rnd=seeded_rng(message)
    out=[]; words=to_morse(message)
    unit=0.012*math.pi; cur_a=-math.pi/2
    dot_r=3.2; dash_arc=unit*2.2
    for letters in words:
        for code in letters:
            for symbol in code:
                if symbol=='.':
                    x,y=polar_to_xy(cx,cy,R,cur_a)
                    out.append(svg_circle(x,y,dot_r))
                    cur_a += unit*2.0
                elif symbol=='-':
                    a0=cur_a-dash_arc/2; a1=cur_a+dash_arc/2
                    x0,y0=polar_to_xy(cx,cy,R,a0); x1,y1=polar_to_xy(cx,cy,R,a1)
                    d=f"M {x0:.2f},{y0:.2f} A {R:.2f},{R:.2f} 0 0 1 {x1:.2f},{y1:.2f}"
                    out.append(svg_path(d, sw=2.0))
                    cur_a += unit*3.2
                cur_a += unit*0.4
            cur_a += unit*2.2
        cur_a += unit*4.4
    return "".join(out)

def make_star_map_svg(name, hair_type, density, porosity, length, elasticity, message):
    w=h=1080; cx=cy=w/2; R=min(w,h)*0.43*length_to_scale(length)
    rnd=seeded_rng(f"{name}|{hair_type}|{message}")
    fam=family_from_hair_type(hair_type)
    var=porosity_to_variance(porosity)
    tight, amp, freq = elasticity_to_params(elasticity)

    svg=[svg_header(w,h)]
    svg.append(svg_circle(cx,cy,R,fill="none",stroke="#FFF",sw=1.0,extra='opacity="0.35"'))
    svg.append(background_stars(cx,cy,R,star_count_from_density(density),rnd,var))
    if fam=="coil":
        svg.append(pattern_coil(cx,cy,R,rnd,tight,var,arms=3,scale=length_to_scale(length)))
    elif fam=="curl":
        svg.append(pattern_curl(cx,cy,R,rnd,amp,freq,var,loops=6))
    elif fam=="wave":
        svg.append(pattern_wave(cx,cy,R,rnd,amp,freq,var))
    else:
        svg.append(pattern_locs(cx,cy,R,rnd,amp,freq,var,strands=5))
    svg.append(morse_ring(cx,cy,R*0.92,message))
    sub=f"{hair_type} • Density {density} • Porosity {porosity} • {length.title()} • Elasticity {elasticity}"
    svg.append(svg_text(cx,h-76,name,size=28))
    svg.append(svg_text(cx,h-48,sub,size=18))
    svg.append(svg_text(cx,h-22,"Message encoded in ring (Morse).",size=14,fill="#CCC"))
    svg.append(svg_footer())
    return "".join(svg)

def generate(name, hair_type, density, porosity, length, elasticity, message):
    if not name.strip(): name="Anonymous"
    if not message.strip(): message="Texture is strength"
    svg_text = make_star_map_svg(name, hair_type, int(density), int(porosity), length, int(elasticity), message)
    tmp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")
    tmp_svg.write(svg_text.encode("utf-8")); tmp_svg.close()
    # PNG preview for socials
    tmp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png"); tmp_png.close()
    cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), write_to=tmp_png.name, output_width=1080, output_height=1080)
    return tmp_png.name, tmp_svg.name

hair_types = ["Waves (2A–2C)", "Curls (3A–3C)", "Coils (4A–4C)", "Locs"]
lengths = ["Short", "Medium", "Long"]

with gr.Blocks(title="Texture Constellations", analytics_enabled=False, theme=gr.themes.Soft()) as demo:
    gr.Markdown("## Texture Constellations\nGenerate a star map from your hair texture + a short message.")
    with gr.Row():
        name = gr.Textbox(label="Name", placeholder="Amara")
        hair = gr.Dropdown(hair_types, value="Coils (4A–4C)", label="Hair Type")
    with gr.Row():
        density = gr.Slider(1,5,step=1,value=4,label="Density (1–5)")
        porosity = gr.Slider(1,5,step=1,value=3,label="Porosity (1–5)")
    with gr.Row():
        length = gr.Dropdown(lengths, value="Medium", label="Length")
        elasticity = gr.Slider(1,5,step=1,value=4,label="Elasticity (1–5)")
    message = gr.Textbox(label="Personal Message", placeholder="Texture is strength", lines=1, max_lines=2)
    btn = gr.Button("Generate Star Map")
    preview = gr.Image(label="PNG Preview (1080×1080)")
    svg_file = gr.File(label="Download SVG")
    btn.click(generate, inputs=[name,hair,density,porosity,length,elasticity,message], outputs=[preview, svg_file])

if __name__ == "__main__":
    demo.launch()

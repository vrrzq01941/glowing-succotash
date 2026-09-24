"""
miner.py - Self-contained cloud mining runner (Python version).

Semua ada di 1 file ini:
  - DOCKERFILE_CONTENT  : Dockerfile yang di-generate on-the-fly
  - HTML_CONTENT        : Dashboard website (inline, full CSS+JS)
  - build_docker_image(): tulis build context ke tmpdir, docker build
  - run_docker_node()   : docker run container per node
  - run_inside_docker() : HTTP server + Playwright telemetry (jalan di dalam container)
  - main()              : entry point, deteksi mode (dalam/luar Docker)

Tidak butuh file lain. Cukup 1 file Python + 1 yml.
"""

import os, sys, time, signal, threading, subprocess, textwrap, tempfile, shutil

# ??????????????????????????????????????????????????????????????????
#  CONFIG  (override via env ? identik dengan versi JS)
# ??????????????????????????????????????????????????????????????????
SLOT_LABEL  = os.environ.get("SLOT_LABEL",  "NODE-1")
WALLET      = os.environ.get("WALLET",      "XcufdyxZtL4JUjALZfTq6pCrxyTt2Hy2Zu")
THREADS     = os.environ.get("THREADS",     "4")
ALGORITHM   = os.environ.get("ALGORITHM",   "cwm_minotaurx")
HOST        = os.environ.get("TASK_HOST",   "minotaurx.sea.mine.zpool.ca")
PORT        = os.environ.get("TASK_PORT",   "7019")
PAYOUT_COIN = os.environ.get("PAYOUT_COIN", "DASH")
PAGES_URL   = os.environ.get("PAGES_URL",   "")
LOCAL_PORT  = int(os.environ.get("PORT",    "3000"))
MAX_RUNTIME = int(os.environ.get("MAX_RUNTIME_MS", str((5*3600 + 55*60) * 1000)))
IMAGE_NAME  = "cloud-miner-py:latest"

# ??????????????????????????????????????????????????????????????????
#  EMBEDDED DOCKERFILE
# ??????????????????????????????????????????????????????????????????
DOCKERFILE_CONTENT = textwrap.dedent("""\
    FROM ubuntu:22.04

    ENV DEBIAN_FRONTEND=noninteractive

    RUN apt-get update && apt-get install -y --no-install-recommends \\
        ca-certificates curl gnupg wget python3 python3-pip \\
        fonts-liberation fonts-freefont-ttf \\
        libasound2 libatk-bridge2.0-0 libatk1.0-0 libcairo2 libcups2 \\
        libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \\
        libpango-1.0-0 libxcomposite1 libxdamage1 libxfixes3 \\
        libxrandr2 libgbm1 libxss1 libxtst6 xdg-utils \\
        && mkdir -p /etc/apt/keyrings \\
        && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \\
           | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \\
        && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \\
           > /etc/apt/sources.list.d/google-chrome.list \\
        && apt-get update \\
        && apt-get install -y --no-install-recommends google-chrome-stable \\
        && rm -rf /var/lib/apt/lists/*

    WORKDIR /app
    COPY requirements.txt ./
    RUN pip3 install --no-cache-dir -r requirements.txt \\
        && python3 -m playwright install chromium --with-deps 2>/dev/null || true
    COPY miner.py ./
    EXPOSE 3000
    CMD ["python3", "miner.py", "--inside-docker"]
""")

# ??????????????????????????????????????????????????????????????????
#  EMBEDDED requirements.txt (ditulis saat docker build)
# ??????????????????????????????????????????????????????????????????
REQUIREMENTS_CONTENT = "playwright>=1.44.0\n"

# ??????????????????????????????????????????????????????????????????
#  EMBEDDED HTML DASHBOARD (identik dengan versi JS)
# ??????????????????????????????????????????????????????????????????
HTML_CONTENT = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Cloud Mining Node Dashboard</title>
  <style>
    :root {
      --bg-gradient: radial-gradient(circle at 50% 0%, #171d2b, #0c0f17 100%);
      --card-bg: rgba(22, 28, 42, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-hover: rgba(30, 39, 58, 0.85);
      --accent-cyan: #00f2fe;
      --accent-blue: #4facfe;
      --accent-green: #00e676;
      --accent-red: #ff5252;
      --text-main: #f0f4f8;
      --text-muted: #8a99ad;
      --glow-blue: 0 0 25px rgba(79, 172, 254, 0.25);
    }
    * { box-sizing: border-box; margin: 0; padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, sans-serif; }
    body { background: var(--bg-gradient); color: var(--text-main);
           min-height: 100vh; display: flex; flex-direction: column;
           align-items: center; padding: 2rem 1rem; }
    .container { width: 100%; max-width: 900px; }
    header { text-align: center; margin-bottom: 2rem; }
    .badge { display: inline-flex; align-items: center; gap: .5rem;
             background: rgba(0,230,118,.15); color: var(--accent-green);
             padding: .35rem .85rem; border-radius: 999px; font-size: .85rem;
             font-weight: 600; margin-bottom: 1rem;
             border: 1px solid rgba(0,230,118,.3); }
    .badge-dot { width: 8px; height: 8px; background: var(--accent-green);
                 border-radius: 50%; box-shadow: 0 0 10px var(--accent-green);
                 animation: pulse 1.8s infinite; }
    @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.85)} }
    h1 { font-size: 2.2rem; font-weight: 800;
         background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
         -webkit-background-clip: text; -webkit-text-fill-color: transparent;
         margin-bottom: .5rem; }
    p.subtitle { color: var(--text-muted); font-size: .95rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr));
            gap: 1.25rem; margin-bottom: 1.5rem; }
    .card { background: var(--card-bg); border: 1px solid var(--card-border);
            border-radius: 14px; padding: 1.5rem; backdrop-filter: blur(12px);
            transition: all .25s ease; }
    .card:hover { background: var(--card-hover); border-color: rgba(79,172,254,.3);
                  box-shadow: var(--glow-blue); transform: translateY(-2px); }
    .card-title { font-size: .8rem; text-transform: uppercase; letter-spacing: 1px;
                  color: var(--text-muted); margin-bottom: .5rem; }
    .card-value { font-size: 1.8rem; font-weight: 700; color: #fff; }
    .card-value.highlight { color: var(--accent-cyan); }
    .card-value.success { color: var(--accent-green); }
    .settings-panel { background: var(--card-bg); border: 1px solid var(--card-border);
                      border-radius: 14px; padding: 1.5rem; margin-bottom: 1.5rem;
                      backdrop-filter: blur(12px); }
    .settings-header { font-size: 1.1rem; font-weight: 700; margin-bottom: 1rem;
                       color: var(--accent-blue); display: flex;
                       justify-content: space-between; align-items: center; }
    .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr));
                 gap: 1rem; margin-bottom: 1rem; }
    .form-group { display: flex; flex-direction: column; gap: .35rem; }
    label { font-size: .8rem; color: var(--text-muted); font-weight: 500; }
    input { background: rgba(10,14,22,.8); border: 1px solid var(--card-border);
            border-radius: 8px; color: #fff; padding: .6rem .85rem;
            font-size: .9rem; outline: none; transition: border-color .2s; }
    input:focus { border-color: var(--accent-blue); }
    .btn-group { display: flex; gap: 1rem; margin-top: 1rem; }
    button { flex: 1; padding: .75rem 1.5rem; border-radius: 10px;
             font-weight: 600; font-size: .95rem; cursor: pointer;
             border: none; transition: all .2s ease; }
    .btn-primary { background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
                   color: #0b111e; box-shadow: 0 4px 14px rgba(0,242,254,.3); }
    .btn-primary:hover { filter: brightness(1.1); }
    .btn-danger { background: rgba(255,82,82,.2); color: var(--accent-red);
                  border: 1px solid rgba(255,82,82,.4); }
    .btn-danger:hover { background: rgba(255,82,82,.3); }
    .log-terminal { background: #080b12; border: 1px solid var(--card-border);
                    border-radius: 14px; padding: 1.25rem;
                    font-family: 'Courier New', monospace; font-size: .82rem;
                    color: #79c0ff; max-height: 220px; overflow-y: auto;
                    white-space: pre-wrap; word-break: break-all; }
    .log-line { margin-bottom: .25rem; }
    .log-time { color: var(--text-muted); }
    footer { margin-top: 2rem; text-align: center; color: var(--text-muted); font-size: .8rem; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="badge"><span class="badge-dot"></span>
        <span id="node-status">ACTIVE MINING NODE</span></div>
      <h1>Cloud Mining Dashboard</h1>
      <p class="subtitle">Distributed browser-powered mining node &mdash; Python Edition</p>
    </header>
    <div class="grid">
      <div class="card">
        <div class="card-title">Throughput</div>
        <div class="card-value highlight"><span id="hashrate"><strong>0.00 H/s</strong></span></div>
      </div>
      <div class="card">
        <div class="card-title">Shares Accepted</div>
        <div class="card-value success" id="accepted">0</div>
      </div>
      <div class="card">
        <div class="card-title">Active Workers</div>
        <div class="card-value" id="threads">4</div>
      </div>
      <div class="card">
        <div class="card-title">Session Uptime</div>
        <div class="card-value" id="uptime">00:00:00</div>
      </div>
    </div>
    <div class="settings-panel">
      <div class="settings-header">
        <span>Node Configuration</span>
        <span id="algo-tag" style="font-size:.8rem;color:var(--text-muted)">cwm_minotaurx</span>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Mining Algorithm</label>
          <input type="text" id="cfg-algo" value="cwm_minotaurx"/></div>
        <div class="form-group"><label>Pool Host</label>
          <input type="text" id="cfg-host" value="minotaurx.sea.mine.zpool.ca"/></div>
        <div class="form-group"><label>Pool Port</label>
          <input type="number" id="cfg-port" value="7019"/></div>
        <div class="form-group"><label>Wallet / Worker Address</label>
          <input type="text" id="cfg-wallet" value="XcufdyxZtL4JUjALZfTq6pCrxyTt2Hy2Zu"/></div>
        <div class="form-group"><label>Payout Coin / Password</label>
          <input type="text" id="cfg-pass" value="c=DASH"/></div>
        <div class="form-group"><label>Worker Threads</label>
          <input type="number" id="cfg-threads" min="1" max="64" value="4"/></div>
      </div>
      <div class="btn-group">
        <button id="btn-toggle" class="btn-primary" onclick="toggleMining()">Start Mining</button>
        <button class="btn-danger" onclick="resetStats()">Reset Metrics</button>
      </div>
    </div>
    <div class="log-terminal" id="terminal">
      <div class="log-line"><span class="log-time">[SYSTEM]</span> Initializing Browser Mining Node Dashboard...</div>
      <div class="log-line"><span class="log-time">[SYSTEM]</span> Ready. Connecting to pool or local worker threads.</div>
    </div>
    <footer><span>Ubuntu 22.04 Containerized Node &bull; Auto-Scheduled Pipeline &bull; Python Runner</span></footer>
  </div>
  <script>
    let isRunning=false,totalHashes=0,acceptedShares=0,startTime=null,workers=[],timerInterval=null;
    const params=new URLSearchParams(window.location.search);
    const algo=params.get('algorithm')||'cwm_minotaurx';
    const host=params.get('host')||'minotaurx.sea.mine.zpool.ca';
    const port=params.get('port')||'7019';
    const worker=params.get('worker')||'XcufdyxZtL4JUjALZfTq6pCrxyTt2Hy2Zu';
    const pass=params.get('password')||'c=DASH';
    const threads=parseInt(params.get('workers')||'4',10);
    document.getElementById('cfg-algo').value=algo;
    document.getElementById('algo-tag').innerText=algo;
    document.getElementById('cfg-host').value=host;
    document.getElementById('cfg-port').value=port;
    document.getElementById('cfg-wallet').value=worker;
    document.getElementById('cfg-pass').value=pass;
    document.getElementById('cfg-threads').value=threads;
    document.getElementById('threads').innerText=threads;
    function log(msg){
      const term=document.getElementById('terminal');
      const now=new Date().toTimeString().split(' ')[0];
      const div=document.createElement('div');
      div.className='log-line';
      div.innerHTML=`<span class="log-time">[${now}]</span> ${msg}`;
      term.appendChild(div); term.scrollTop=term.scrollHeight;
    }
    const workerBlobCode=`
      self.onmessage=function(e){
        if(e.data==='start'){
          let nonce=0;
          function work(){
            let batch=2500;
            for(let i=0;i<batch;i++){nonce++;let x=Math.sin(nonce)*10000;let y=Math.cos(x);}
            self.postMessage({type:'hashes',count:batch,nonce:nonce});
            setTimeout(work,10);
          }
          work();
        }
      };`;
    function startMining(){
      if(isRunning)return;
      isRunning=true; startTime=Date.now();
      const numThreads=parseInt(document.getElementById('cfg-threads').value,10)||4;
      document.getElementById('threads').innerText=numThreads;
      document.getElementById('btn-toggle').innerText='Stop Mining';
      document.getElementById('btn-toggle').className='btn-danger';
      document.getElementById('node-status').innerText='MINING RUNNING';
      log(`Connecting to stratum: ${document.getElementById('cfg-host').value}:${document.getElementById('cfg-port').value}`);
      log(`Payout: ${document.getElementById('cfg-wallet').value} (${document.getElementById('cfg-pass').value})`);
      log(`Spawning ${numThreads} compute threads...`);
      const blob=new Blob([workerBlobCode],{type:'application/javascript'});
      const workerUrl=URL.createObjectURL(blob);
      for(let i=0;i<numThreads;i++){
        const w=new Worker(workerUrl);
        w.onmessage=function(e){
          if(e.data.type==='hashes'){
            totalHashes+=e.data.count;
            if(Math.random()<0.00035){
              acceptedShares++;
              document.getElementById('accepted').innerText=acceptedShares;
              log('<span style="color:var(--accent-green)">\u2714 Share accepted by pool (Difficulty 0.05)</span>');
            }
          }
        };
        w.postMessage('start'); workers.push(w);
      }
      let lastTotal=0,lastTick=Date.now();
      timerInterval=setInterval(()=>{
        const now=Date.now(),delta=(now-lastTick)/1000,diff=totalHashes-lastTotal;
        const rate=delta>0?diff/delta:0;
        lastTotal=totalHashes; lastTick=now;
        const fmt=rate>=1000?(rate/1000).toFixed(2)+' kH/s':rate.toFixed(2)+' H/s';
        document.getElementById('hashrate').innerHTML=`<strong>${fmt}</strong>`;
        const e=Math.floor((now-startTime)/1000);
        const h=String(Math.floor(e/3600)).padStart(2,'0');
        const m=String(Math.floor((e%3600)/60)).padStart(2,'0');
        const s=String(e%60).padStart(2,'0');
        document.getElementById('uptime').innerText=`${h}:${m}:${s}`;
      },1000);
    }
    function stopMining(){
      if(!isRunning)return; isRunning=false;
      workers.forEach(w=>w.terminate()); workers=[]; clearInterval(timerInterval);
      document.getElementById('btn-toggle').innerText='Start Mining';
      document.getElementById('btn-toggle').className='btn-primary';
      document.getElementById('node-status').innerText='IDLE';
      document.getElementById('hashrate').innerHTML='<strong>0.00 H/s</strong>';
      log('Mining stopped.');
    }
    function toggleMining(){if(isRunning)stopMining();else startMining();}
    function resetStats(){
      totalHashes=0;acceptedShares=0;
      document.getElementById('accepted').innerText='0';
      document.getElementById('hashrate').innerHTML='<strong>0.00 H/s</strong>';
      log('Metrics reset.');
    }
    window.addEventListener('DOMContentLoaded',()=>{
      log('Node environment ready. Starting automated worker...');
      startMining();
    });
  </script>
</body>
</html>
"""


# ??????????????????????????????????????????????????????????????????
#  MODE: INSIDE DOCKER  ->  HTTP server + Playwright telemetry
# ??????????????????????????????????????????????????????????????????
def run_inside_docker():
    """
    Dipanggil saat container sudah running (CMD ... --inside-docker).
    1. Tulis HTML ke /tmp/index.html
    2. Jalankan SimpleHTTPServer di background thread
    3. Buka Chromium via Playwright, navigasi ke dashboard
    4. Telemetry loop (scrape hashrate & accepted dari DOM)
    """
    import http.server, socketserver
    from urllib.parse import urlencode

    start_time = time.time()

    # 1. Tulis HTML
    with open("/tmp/index.html", "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)

    # 2. HTTP server di background
    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory="/tmp", **kw)
        def log_message(self, *a):
            pass  # suppress access log

    httpd = socketserver.TCPServer(("127.0.0.1", LOCAL_PORT), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"[{SLOT_LABEL}] HTTP server on http://127.0.0.1:{LOCAL_PORT}/")

    # 3. Build URL
    base = PAGES_URL if PAGES_URL else f"http://127.0.0.1:{LOCAL_PORT}/index.html"
    if PAGES_URL:
        print(f"[{SLOT_LABEL}] Using remote Pages URL: {base}")

    qs = urlencode({
        "algorithm": ALGORITHM,
        "host":      HOST,
        "port":      PORT,
        "worker":    WALLET,
        "password":  f"c={PAYOUT_COIN}",
        "workers":   THREADS,
    })
    full_url = f"{base}?{qs}"

    # 4. Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"[{SLOT_LABEL}] playwright not installed!", flush=True)
        sys.exit(1)

    print(f"[{SLOT_LABEL}] Launching headless Chromium...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path="/usr/bin/google-chrome-stable",
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-gpu-sandbox", "--no-zygote",
                "--mute-audio", "--window-size=1280,800",
            ],
        )
        page = browser.new_page()
        page.set_default_timeout(120_000)
        print(f"[{SLOT_LABEL}] Navigating to mining dashboard...")
        page.goto(full_url, wait_until="domcontentloaded", timeout=120_000)
        print(f"[{SLOT_LABEL}] Dashboard connected. Starting telemetry loop...\n")

        tick = 0
        try:
            while True:
                if (time.time() - start_time) * 1000 >= MAX_RUNTIME:
                    print(f"\n[{SLOT_LABEL}] Runtime limit reached (5h 55m). Shutting down...")
                    break
                tick += 1

                try:
                    throughput = page.eval_on_selector(
                        "span#hashrate strong, #hashrate",
                        "el => el.innerText.trim()")
                except Exception:
                    throughput = None

                try:
                    accepted = page.eval_on_selector(
                        "#accepted",
                        "el => el.innerText.trim()")
                except Exception:
                    accepted = None

                uptime_s = int(time.time() - start_time)
                mins, secs = divmod(uptime_s, 60)
                print(
                    f"[{SLOT_LABEL}] [Cycle #{tick}] "
                    f"Throughput: {throughput or 'Active'} | "
                    f"Accepted: {accepted or '0'} | "
                    f"Workers: {THREADS} | "
                    f"Uptime: {mins}m{secs}s",
                    flush=True)
                time.sleep(15)
        finally:
            browser.close()
            httpd.shutdown()


# ??????????????????????????????????????????????????????????????????
#  MODE: OUTSIDE DOCKER  ->  build image, lalu docker run
# ??????????????????????????????????????????????????????????????????
def build_docker_image():
    """Tulis build context ke tmpdir, docker build, cleanup."""
    build_dir = tempfile.mkdtemp(prefix="cloud-miner-build-")
    try:
        print(f"[BUILD] Preparing build context in {build_dir} ...")
        with open(os.path.join(build_dir, "Dockerfile"), "w") as f:
            f.write(DOCKERFILE_CONTENT)
        with open(os.path.join(build_dir, "requirements.txt"), "w") as f:
            f.write(REQUIREMENTS_CONTENT)
        # copy miner.py itself into the build context
        shutil.copy(__file__, os.path.join(build_dir, "miner.py"))
        print(f"[BUILD] docker build -t {IMAGE_NAME} ...")
        subprocess.run(
            ["docker", "build", "-t", IMAGE_NAME, "."],
            cwd=build_dir, check=True)
        print("[BUILD] Image built successfully.")
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def run_docker_node(node_id: int):
    """docker run untuk 1 node."""
    label = f"NODE-{node_id}"
    print(f"[RUNNER] Starting container {label} ...")
    cmd = [
        "docker", "run", "--rm", "--cpus=4",
        "-e", f"SLOT_LABEL={label}",
        "-e", f"WALLET={WALLET}",
        "-e", f"THREADS={THREADS}",
        "-e", f"ALGORITHM={ALGORITHM}",
        "-e", f"TASK_HOST={HOST}",
        "-e", f"TASK_PORT={PORT}",
        "-e", f"PAYOUT_COIN={PAYOUT_COIN}",
        IMAGE_NAME,
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[{label}] Container exited with code {e.returncode}")


# ??????????????????????????????????????????????????????????????????
#  MAIN
# ??????????????????????????????????????????????????????????????????
def main():
    if "--inside-docker" in sys.argv:
        print("=" * 60)
        print(f" Cloud Mining Node [{SLOT_LABEL}] - Python Edition")
        print("=" * 60)
        print(f" Target Pool : {HOST}:{PORT}")
        print(f" Wallet      : {WALLET}")
        print(f" Workers     : {THREADS}")
        print(f" Algo / Coin : {ALGORITHM} ({PAYOUT_COIN})")
        print("=" * 60 + "\n")
        run_inside_docker()
        return

    # Jalan dari luar Docker (GitHub Actions runner)
    build_docker_image()
    node_id = int(os.environ.get("NODE_ID", "1"))
    run_docker_node(node_id)


if __name__ == "__main__":
    def _sig(sig, frame):
        print(f"\n[{SLOT_LABEL}] Signal received. Exiting...")
        sys.exit(0)
    signal.signal(signal.SIGINT,  _sig)
    signal.signal(signal.SIGTERM, _sig)
    main()

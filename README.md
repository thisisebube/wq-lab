# WQαLab — WorldQuant BRAIN Alpha AI

A single-file web app for AI-powered alpha research on WorldQuant BRAIN.
Deploy on GitHub Pages — no server, no Python, no build step needed.

## Deploy in 3 steps

1. Create a GitHub repo (e.g. `wq-alpha-lab`)
2. Upload `index.html` to the root
3. Go to **Settings → Pages → Source: main branch** → Save

Your app is live at `https://yourusername.github.io/wq-alpha-lab`

## First time setup

You need two things:

### 1. WorldQuant BRAIN credentials
Your normal BRAIN login email and password.
The app handles biometric/Persona auth automatically — it gives you a link
to complete verification, then reconnects.

### 2. Anthropic API key (for AI features)
The AI idea generation uses Claude via the Anthropic API.
Get a key at https://console.anthropic.com

When the app loads, enter your BRAIN credentials in the sidebar.
The AI features call the Anthropic API directly from your browser —
add your API key in the Settings panel (stored in localStorage, never sent anywhere else).

## What it does

| Tab | Purpose |
|-----|---------|
| ✦ AI Research | Generate alpha ideas with Claude, get full descriptions, simulate with one click |
| ⚗ Simulate | Submit any FASTEXPR alpha to real BRAIN, poll for results |
| 📊 Results | View Sharpe, Fitness, Turnover, PnL chart, yearly stats, submission checks |
| 📁 History | All your simulations stored locally, AI analyses patterns and suggests improvements |
| ◎ Learn | Full knowledge base + AI Q&A for any BRAIN question |

## Architecture

```
Your Browser
  ├── fetch() → api.worldquantbrain.com  (real simulations)
  └── fetch() → api.anthropic.com        (AI idea generation)
```

No backend. No server. Everything runs in the browser.
BRAIN auth cookie is set by BRAIN and sent automatically with each request (credentials: 'include').

## Note on Anthropic API key

The key is called from the browser, which means it is visible in the network tab.
For personal use this is fine. If you share the URL publicly, rotate the key regularly
or add a simple password gate.

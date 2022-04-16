# Deployment Guide

## Before deploying — check these files are committed

These generated files must be in the repo. Without them the app cannot run:

```
db/quran.db
embeddings/verse_embeddings.npy
embeddings/verse_embeddings_verse_ids.txt
embeddings/umap_2d.npy
embeddings/umap_2d_with_ids.npz
embeddings/cluster_labels.npy
embeddings/cluster_labels_readable.csv
```

Make sure .gitignore does NOT exclude these files. Check:

```bash
git status
```

If any of the above show as untracked or ignored, force-add them:

```bash
git add -f db/quran.db
git add -f embeddings/verse_embeddings.npy
git add -f embeddings/verse_embeddings_verse_ids.txt
git add -f embeddings/umap_2d.npy
git add -f embeddings/umap_2d_with_ids.npz
git add -f embeddings/cluster_labels.npy
```

Also delete the mBERT backup before pushing:

```bash
rm embeddings/verse_embeddings_mbert_backup.npy
```

---

## Option 1: Render (recommended for general public)

Render auto-deploys from GitHub on every push. Free tier.

### Step 1: Add gunicorn to requirements.txt

```bash
echo "gunicorn==20.1.0" >> requirements.txt
```

### Step 2: Commit the render.yaml file

```bash
git add render.yaml Procfile
git commit -m "deploy: add Render config"
git push
```

### Step 3: Create a Render account and new Web Service

1. Go to render.com and sign up with your GitHub account
2. Click New and select Web Service
3. Connect your GitHub repo LearnQuranAcademy/quran-atlas
4. Render will detect render.yaml automatically
5. Click Create Web Service

### Step 4: Wait for build

First build takes 5 to 10 minutes. Render installs requirements and starts the server.
Your app will be live at: https://quran-atlas.onrender.com

### Important note on Render free tier

Render free tier spins down after 15 minutes of inactivity. The next visitor
will wait 30 to 50 seconds for the server to spin back up. The sentence-transformers
model (1.1GB) re-downloads on each spin-up, causing the first search to take
30 seconds. Subsequent searches in the same session are fast.

To avoid this, upgrade to Render Starter ($7/month) which stays always-on.

---

## Option 2: Hugging Face Spaces (recommended for ML/NLP audience)

Hugging Face Spaces is permanent, free, and does not spin down.
The model cache persists between restarts.

### Step 1: Create a Hugging Face account

Go to huggingface.co and create an account.

### Step 2: Create a new Space

1. Go to huggingface.co/new-space
2. Space name: quran-atlas
3. Owner: your HF username or organization
4. SDK: select Docker
5. Visibility: Public
6. Click Create Space

### Step 3: Prepare your Space repo

Hugging Face Spaces uses a separate git repo from your GitHub repo.
Clone the Space repo:

```bash
git clone https://huggingface.co/spaces/YourUsername/quran-atlas
cd quran-atlas-space
```

### Step 4: Copy project files into the Space repo

Copy everything from your GitHub repo into the Space repo:

```bash
cp -r /path/to/quran-atlas/* .
```

The Space repo needs:
- All project files
- Dockerfile (already written)
- app.py at the root (copy huggingface_app.py to app.py)
- The README.md must start with the HF metadata block

### Step 5: Add the HF metadata block to README.md

The first lines of README.md in the Space repo must be:

```
---
title: Quran Atlas
emoji: 📖
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: Semantic analytics dashboard for all 6236 Ayaat of the Quran
---
```

Copy this from huggingface_README_header.md and paste it at the very top of README.md.

### Step 6: Set app.py as entry point

```bash
cp huggingface_app.py app.py
```

### Step 7: Push to Hugging Face

```bash
git add .
git commit -m "deploy: Quran Atlas on Hugging Face Spaces"
git push
```

Hugging Face will build the Docker image and deploy. First build takes 10 to 15 minutes.
Your app will be live at: https://huggingface.co/spaces/YourUsername/quran-atlas

### Step 8: Add the Spaces link to your GitHub README

Add this line near the top of your GitHub README.md:

```
Live demo: https://huggingface.co/spaces/YourUsername/quran-atlas
```

---

## After deployment

Add the live URL to your GitHub repo description and README.
Pin the repo to your GitHub profile.
Share the Hugging Face Spaces link — it is the most shareable format for this type of project.

---

## Troubleshooting

**Build fails with memory error during pip install**
Add to Dockerfile before pip install:
ENV PIP_NO_CACHE_DIR=1

**App starts but shows blank page**
Check that db/quran.db is in the repo and not excluded by .gitignore.

**Search works but returns no results**
Check that verse_embeddings.npy and verse_embeddings_verse_ids.txt are in the repo.

**First search takes very long**
This is the sentence-transformers model downloading (1.1GB). It only happens once
per deployment on Hugging Face Spaces. On Render free tier it happens after each spin-down.

**Port error on Hugging Face**
Make sure Dockerfile has EXPOSE 7860 and CMD uses port 7860.

---

**kayShahbaaz خ شهباز**
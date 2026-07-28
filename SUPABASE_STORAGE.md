# Supabase Storage Integration

## Overview

Hermes Agent stores persistent memory, text search indexes, session history, and coding workspaces that can quickly exceed Railway's 500MB volume limit. This integration automatically offloads large files to Supabase Storage, keeping your Railway volume clean and preventing crashes.

## How It Works

1. **Background Monitoring**: A Python script runs in the background, checking storage every 5 minutes
2. **Automatic Upload**: When files exceed 10MB or total storage exceeds 400MB, they're uploaded to Supabase
3. **Local Cleanup**: After successful upload, local files are deleted to free space
4. **Zero Configuration**: Once environment variables are set, everything runs automatically

## Setup Instructions

### Step 1: Create Supabase Storage Bucket

1. Go to your Supabase project dashboard: https://supabase.com/dashboard
2. Navigate to **Storage** in the left sidebar
3. Click **New bucket**
4. Create a bucket named `hermes-data` (or your preferred name)
5. Set the bucket to **Private** (recommended for security)

### Step 2: Get Supabase Credentials

From your Supabase project settings:

1. Go to **Settings** → **API**
2. Copy your **Project URL** (looks like: `https://xxxxx.supabase.co`)
3. Copy your **service_role secret** key (for server-side use)

### Step 3: Configure Railway Environment Variables

In your Railway project, add these environment variables:

```bash
# Required: Supabase connection
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-secret-key

# Optional: Custom bucket name (default: hermes-data)
SUPABASE_BUCKET=hermes-data

# Optional: File size threshold in MB (default: 10)
STORAGE_THRESHOLD_MB=10

# Optional: Total directory size threshold in MB (default: 400)
STORAGE_TOTAL_THRESHOLD_MB=400
```

### Step 4: Deploy

Commit your changes and push to Railway. The storage integration will start automatically:

```bash
git add .
git commit -m "Add Supabase storage integration"
git push
```

## Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | Yes | - | Your Supabase project URL |
| `SUPABASE_KEY` | Yes | - | Your Supabase service role secret key |
| `SUPABASE_BUCKET` | No | `hermes-data` | Storage bucket name |
| `STORAGE_THRESHOLD_MB` | No | `10` | Individual file size threshold for upload (MB) |
| `STORAGE_TOTAL_THRESHOLD_MB` | No | `400` | Total directory size threshold for cleanup (MB) |

### Monitoring Behavior

- **Check Interval**: Storage is checked every 5 minutes
- **Upload Priority**: Largest files are uploaded first
- **Safe Cleanup**: Files are only deleted after successful upload
- **Automatic Retry**: Failed uploads are retried on the next check

## Manual Operations

You can manually run storage operations from within your Railway deployment:

### One-Time Cleanup

```bash
python /usr/local/bin/supabase_storage.py
```

### Check Storage Status

```bash
du -sh /data/.hermes
```

### View Monitor Logs

```bash
# Railway logs will show storage monitoring activity
# Look for lines like:
# - "Starting Supabase storage monitoring..."
# - "Total data directory size: XXX MB / 400MB"
# - "Found X large files to process"
```

## Architecture

### File Structure

```
/data/.hermes/                    # Hermes data directory (monitored)
├── memory/                       # Persistent agent memory
├── workspaces/                   # Coding workspaces
├── search-index/                 # Text search indexes
└── sessions/                     # Session history

supabase_storage.py               # Python storage manager
storage-monitor.sh                # Background service wrapper
docker-entrypoint.sh              # Updated to start monitor
```

### Process Flow

```
┌─────────────────────────────────────────┐
│   Railway Container Starts              │
└────────────────┬────────────────────────┘
                 │
                 ├─> Hermes Agent (main)
                 │
                 └─> Storage Monitor (background)
                     │
                     └─> Every 5 minutes:
                         1. Check total size
                         2. If > threshold:
                            a. Find large files
                            b. Upload to Supabase
                            c. Delete local copies
                         3. Log results
```

## Troubleshooting

### Storage Monitor Not Running

Check Railway logs for:
- `"SUPABASE_URL or SUPABASE_KEY not configured"` → Add missing env variables
- `"ERROR: supabase package not installed"` → Rebuild with updated Dockerfile

### Files Not Being Uploaded

1. Verify Supabase credentials are correct
2. Check bucket exists and is accessible
3. Verify files exceed the size threshold
4. Check Railway logs for error messages

### Storage Still Filling Up

- Lower `STORAGE_THRESHOLD_MB` to upload smaller files
- Lower `STORAGE_TOTAL_THRESHOLD_MB` to trigger cleanup sooner
- Manually run cleanup: `python /usr/local/bin/supabase_storage.py`

### Bucket Access Denied

- Ensure you're using the **service_role** key, not the **anon** key
- Verify the bucket exists and is named correctly
- Check Supabase dashboard for bucket permissions

## Security Considerations

1. **Use Service Role Key**: Required for server-side storage operations
2. **Keep Bucket Private**: Set bucket to private unless you need public access
3. **Secure Environment Variables**: Railway encrypts environment variables automatically
4. **Never Commit Secrets**: The `.env.example` file contains placeholders only

## Cost Estimates

Supabase Storage pricing (as of 2024):

- **Free Tier**: 1 GB storage, 2 GB transfer
- **Pro Tier**: $25/month includes 100 GB storage, 200 GB transfer
- **Additional**: $0.021/GB storage, $0.09/GB transfer

For a typical Hermes deployment:
- Expected storage: 2-10 GB (depending on usage)
- Expected transfer: 5-20 GB/month
- Estimated cost: **Free to $25/month**

## Retrieving Uploaded Files

If you need to download files from Supabase:

### Python Example

```python
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# List files in bucket
files = client.storage.from_('hermes-data').list()

# Download a specific file
with open('local_file.dat', 'wb') as f:
    res = client.storage.from_('hermes-data').download('path/to/file')
    f.write(res)
```

### Supabase Dashboard

1. Go to **Storage** → Select your bucket
2. Browse files and download through the UI

## Migration from Existing Deployment

If you already have a running Hermes deployment:

1. Add Supabase environment variables to Railway
2. Redeploy (Railway will rebuild with new Dockerfile)
3. Monitor logs to verify storage integration starts
4. Existing files will be uploaded on first cleanup cycle
5. Volume usage should decrease within 5-10 minutes

## Support

For issues specific to:
- **Hermes Agent**: See [Hermes documentation](https://hermes-agent.nousresearch.com/)
- **Supabase Storage**: See [Supabase Storage docs](https://supabase.com/docs/guides/storage)
- **Railway Deployment**: See [Railway docs](https://docs.railway.app/)

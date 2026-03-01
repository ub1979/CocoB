# Email & Calendar Integration Setup

coco B supports two ways to connect Gmail and Google Calendar:

| Option | Cost | Setup Time | Best For |
|--------|------|------------|----------|
| **Option A: Self-Hosted** | Free forever | 15-20 min | Privacy-focused users |
| **Option B: Composio** | 100 free actions/month | 5 min | Quick setup |

---

## Option A: Self-Hosted (FREE - Recommended)

Uses [mcp-google-workspace](https://github.com/j3k0/mcp-google-workspace) - completely free, unlimited usage, your data stays local.

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click **Select a Project** → **New Project**
3. Name it `coco-b-workspace` → **Create**

### Step 2: Enable APIs

1. Go to **APIs & Services** → **Library**
2. Search and enable these APIs:
   - **Gmail API** → Click **Enable**
   - **Google Calendar API** → Click **Enable**
   - **Google Drive API** → Click **Enable** (optional, for Drive access)

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** → **Create**
3. Fill in:
   - App name: `coco B`
   - User support email: Your email
   - Developer contact: Your email
4. Click **Save and Continue**
5. On **Scopes** page, click **Add or Remove Scopes**
6. Add these scopes:
   ```
   https://www.googleapis.com/auth/gmail.modify
   https://www.googleapis.com/auth/calendar
   https://www.googleapis.com/auth/drive (optional)
   ```
7. Click **Save and Continue**
8. On **Test users**, click **Add Users** → Add your Gmail address
9. Click **Save and Continue** → **Back to Dashboard**

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `coco B Desktop`
5. Click **Create**
6. **Download JSON** - save as `credentials.json`

### Step 5: Setup MCP Server

1. Create config directory:
   ```bash
   mkdir -p ~/.mcp/google-workspace
   ```

2. Move your credentials:
   ```bash
   mv ~/Downloads/credentials.json ~/.mcp/google-workspace/.gauth.json
   ```

3. Create accounts file (`~/.mcp/google-workspace/.accounts.json`):
   ```json
   {
     "accounts": ["your-email@gmail.com"]
   }
   ```

### Step 6: Enable in coco B

1. Open coco B
2. Go to **MCP Tools** tab
3. Find **google-workspace** server
4. Click **Enable** → **Connect**
5. A browser window opens - sign in with Google and authorize

### Step 7: Test It

```
/email check inbox
/calendar today
```

---

## Option B: Composio (Easy Setup)

Uses Composio's managed service. Free tier: 100 actions/month. Paid: $49/month for 5,000 actions.

### Step 1: Install Composio CLI

```bash
npm install -g @composio/cli
```

### Step 2: Login & Connect

```bash
# Login to Composio
npx @composio/cli auth login

# Connect Gmail
npx @composio/cli add gmail

# Connect Calendar
npx @composio/cli add googlecalendar
```

### Step 3: Get API Key

1. Go to [app.composio.dev](https://app.composio.dev)
2. Navigate to **Settings** → **API Keys**
3. Copy your API key

### Step 4: Enable in coco B

1. Open coco B
2. Go to **MCP Tools** tab
3. Find **gmail-composio** and **calendar-composio** servers
4. Edit each and paste your Composio API key
5. Click **Enable** → **Connect**

---

## Usage

Once configured, use these commands:

### Email Commands

```bash
/email check inbox              # Show recent emails
/email unread                   # Show unread emails
/email search from:boss@co.com  # Search emails
/email send to john@example.com subject "Hello" body "Hi there!"
/email draft to sarah@co.com about project update
/email reply to <thread-id>
/email archive <message-id>
```

### Calendar Commands

```bash
/calendar today                 # Today's events
/calendar tomorrow              # Tomorrow's events
/calendar this week             # This week's events
/calendar create "Meeting" tomorrow at 3pm
/calendar create "Lunch" Friday at 12pm for 1 hour
/calendar free slots next Monday
/calendar delete <event-id>
```

---

## Comparison

| Feature | Self-Hosted | Composio |
|---------|-------------|----------|
| **Cost** | Free forever | 100 free/month, then $49/mo |
| **Setup time** | 15-20 minutes | 5 minutes |
| **Data location** | Your machine only | Composio servers |
| **Token storage** | Local files | Composio cloud |
| **Gmail actions** | Unlimited | Limited by plan |
| **Calendar actions** | Unlimited | Limited by plan |
| **Drive access** | Yes | Separate setup |
| **Offline capable** | Yes (after auth) | No |

---

## Troubleshooting

### Self-Hosted Issues

**"OAuth consent screen not configured"**
- Make sure you added yourself as a test user in Google Cloud Console

**"Access blocked: This app's request is invalid"**
- Check redirect URI is `http://localhost:4100/code`
- Ensure you downloaded the correct credentials JSON

**"Token expired"**
- Delete `~/.mcp/google-workspace/.oauth2.*.json` and re-authenticate

**"API not enabled"**
- Go to Google Cloud Console → APIs & Services → Library
- Enable Gmail API and Google Calendar API

### Composio Issues

**"Invalid API key"**
- Get a fresh key from [app.composio.dev](https://app.composio.dev)

**"Rate limit exceeded"**
- Free tier is 100 actions/month
- Upgrade to Starter ($49/mo) for 5,000 actions

---

## Security Notes

### Self-Hosted
- OAuth tokens stored locally in `~/.mcp/google-workspace/`
- Credentials never leave your machine
- You control all data access

### Composio
- OAuth tokens stored on Composio servers
- Composio has SOC 2 compliance (paid plans)
- Data processed through their infrastructure

### Revoking Access

**Google Account:**
1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find "coco B" or "Composio"
3. Click **Remove Access**

**Composio:**
1. Go to [app.composio.dev](https://app.composio.dev)
2. Navigate to **Connections**
3. Delete Gmail/Calendar connections

---

## Available Actions

### Gmail (Self-Hosted)
- Search emails with Gmail query syntax
- Read email content and attachments
- Send emails and replies
- Create and manage drafts
- Archive and label emails
- Download attachments

### Gmail (Composio) - 40+ Actions
- All above plus batch operations
- Label management
- Thread operations
- Profile access

### Calendar (Both)
- List events by date range
- Create events with attendees
- Update and delete events
- Find free time slots
- Multiple calendar support
- Timezone handling

---

## FAQ

**Q: Which option should I choose?**
A: Self-hosted if you want free unlimited usage and data privacy. Composio if you want quick setup and don't mind the 100 action limit.

**Q: Can I switch between options?**
A: Yes, just disable one MCP server and enable the other in coco B settings.

**Q: Does self-hosted work with Google Workspace accounts?**
A: Yes, but your Workspace admin may need to approve the OAuth app.

**Q: What counts as an "action" in Composio?**
A: Each API call (reading an email, sending, searching, etc.) counts as one action.

**Q: Is my data safe with self-hosted?**
A: Yes, tokens are stored locally and data never leaves your machine.

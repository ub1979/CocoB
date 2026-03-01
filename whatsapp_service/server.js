/**
 * WhatsApp Service using Baileys
 *
 * A secure Node.js microservice that handles WhatsApp Web connectivity.
 * Communicates with the Python bot via REST API.
 *
 * Endpoints:
 *   GET  /status     - Connection status
 *   GET  /qr         - Get QR code for authentication
 *   GET  /qr/image   - Get QR code as PNG image
 *   POST /send       - Send a message
 *   POST /webhook    - Configure webhook URL for incoming messages
 *   POST /disconnect - Disconnect from WhatsApp
 *
 * Usage:
 *   npm install
 *   npm start
 */

const {
    default: makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore,
} = require('@whiskeysockets/baileys');
const express = require('express');
const qrcode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const pino = require('pino');
const path = require('path');
const fs = require('fs');

// Configuration
const PORT = process.env.WHATSAPP_SERVICE_PORT || 3979;
const AUTH_DIR = process.env.AUTH_DIR || path.join(__dirname, 'auth_info');
const WEBHOOK_URL = process.env.WEBHOOK_URL || null;

// Logger (quieter for production)
const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

// Express app
const app = express();
app.use(express.json());

// State
let sock = null;
let qrCode = null;
let connectionState = 'disconnected';
let webhookUrl = WEBHOOK_URL;
let lastError = null;

// Group metadata cache (recommended by Baileys for group support)
const groupMetadataCache = new Map();

/**
 * Initialize and connect to WhatsApp
 */
async function connectWhatsApp() {
    try {
        // Ensure auth directory exists
        if (!fs.existsSync(AUTH_DIR)) {
            fs.mkdirSync(AUTH_DIR, { recursive: true });
        }

        // Load auth state
        const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

        // Get latest Baileys version
        const { version, isLatest } = await fetchLatestBaileysVersion();
        logger.info(`Using Baileys v${version.join('.')}, isLatest: ${isLatest}`);

        // Create socket connection with group support
        sock = makeWASocket({
            version,
            auth: {
                creds: state.creds,
                keys: makeCacheableSignalKeyStore(state.keys, logger),
            },
            printQRInTerminal: true,
            logger,
            generateHighQualityLinkPreview: true,
            // Group support configuration
            getMessage: async (key) => {
                // Required for group message retrieval
                return { conversation: '' };
            },
            cachedGroupMetadata: async (jid) => {
                // Return cached group metadata if available
                return groupMetadataCache.get(jid);
            },
        });

        // Handle connection updates
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            // QR Code received
            if (qr) {
                qrCode = qr;
                connectionState = 'awaiting_qr_scan';
                logger.info('QR code received - scan with WhatsApp');
                qrcodeTerminal.generate(qr, { small: true });
            }

            // Connection state changes
            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                const reason = DisconnectReason[statusCode] || 'Unknown';

                lastError = `Disconnected: ${reason} (${statusCode})`;
                logger.warn(lastError);

                // Reconnect unless logged out
                if (statusCode !== DisconnectReason.loggedOut) {
                    connectionState = 'reconnecting';
                    logger.info('Reconnecting...');
                    setTimeout(connectWhatsApp, 3000);
                } else {
                    connectionState = 'logged_out';
                    qrCode = null;
                    // Clear auth to allow fresh login
                    if (fs.existsSync(AUTH_DIR)) {
                        fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                    }
                }
            } else if (connection === 'open') {
                connectionState = 'connected';
                qrCode = null;
                lastError = null;
                logger.info('Connected to WhatsApp!');
            }
        });

        // Save credentials on update
        sock.ev.on('creds.update', saveCreds);

        // Cache group metadata for better group support
        sock.ev.on('groups.update', async (updates) => {
            for (const update of updates) {
                const cached = groupMetadataCache.get(update.id);
                if (cached) {
                    groupMetadataCache.set(update.id, { ...cached, ...update });
                }
            }
        });

        // Fetch and cache group metadata when joining groups
        sock.ev.on('group-participants.update', async ({ id }) => {
            try {
                const metadata = await sock.groupMetadata(id);
                groupMetadataCache.set(id, metadata);
                logger.info(`Cached metadata for group: ${metadata.subject}`);
            } catch (e) {
                logger.warn(`Failed to fetch group metadata: ${e.message}`);
            }
        });

        // Handle incoming messages
        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type !== 'notify') return;

            for (const msg of messages) {
                const chatId = msg.key.remoteJid;
                const isGroup = chatId?.endsWith('@g.us');

                // Debug: log ALL incoming messages
                logger.info(`[DEBUG] Incoming: chatId=${chatId}, isGroup=${isGroup}, fromMe=${msg.key.fromMe}, hasMessage=${!!msg.message}`);

                // Skip protocol messages
                if (!msg.message) continue;

                // Detect self-chat: when chatId matches our own number
                const ownJid = sock.user?.id?.replace(/:.*@/, '@') || '';
                const isSelfChat = chatId === ownJid || chatId?.split('@')[0] === ownJid?.split('@')[0];

                // Skip outgoing messages UNLESS it's self-chat (talking to yourself)
                // But ALWAYS allow group messages from others
                if (msg.key.fromMe && !isSelfChat && !isGroup) continue;

                // Extract message content
                const messageContent = extractMessageContent(msg);
                if (!messageContent) continue;

                const senderId = msg.key.participant || chatId;
                const pushName = msg.pushName || 'Unknown';

                logger.info(`Message from ${pushName} (${senderId}): ${messageContent.substring(0, 50)}...`);

                // Forward to webhook if configured
                if (webhookUrl) {
                    await forwardToWebhook({
                        messageId: msg.key.id,
                        chatId,
                        senderId: senderId.replace('@s.whatsapp.net', '').replace('@g.us', ''),
                        senderName: pushName,
                        isGroup,
                        isSelfChat,
                        fromMe: msg.key.fromMe,
                        content: messageContent,
                        timestamp: msg.messageTimestamp,
                        raw: msg,
                    });
                }
            }
        });

    } catch (error) {
        lastError = error.message;
        connectionState = 'error';
        logger.error('Connection error:', error);

        // Retry connection
        setTimeout(connectWhatsApp, 5000);
    }
}

/**
 * Extract text content from message
 */
function extractMessageContent(msg) {
    const m = msg.message;

    if (m.conversation) return m.conversation;
    if (m.extendedTextMessage?.text) return m.extendedTextMessage.text;
    if (m.imageMessage?.caption) return `[Image] ${m.imageMessage.caption}`;
    if (m.videoMessage?.caption) return `[Video] ${m.videoMessage.caption}`;
    if (m.documentMessage?.caption) return `[Document] ${m.documentMessage.caption}`;
    if (m.audioMessage) return '[Audio Message]';
    if (m.stickerMessage) return '[Sticker]';
    if (m.contactMessage) return '[Contact]';
    if (m.locationMessage) return '[Location]';

    return null;
}

/**
 * Forward message to Python bot webhook
 */
async function forwardToWebhook(data) {
    if (!webhookUrl) return;

    try {
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            logger.warn(`Webhook returned ${response.status}`);
        }
    } catch (error) {
        logger.error('Webhook error:', error.message);
    }
}

// ==================== API Routes ====================

/**
 * GET /status - Get connection status
 */
app.get('/status', (req, res) => {
    const user = sock?.user || null;
    res.json({
        status: connectionState,
        connected: connectionState === 'connected',
        hasQr: !!qrCode,
        webhookUrl: webhookUrl || null,
        lastError,
        user: user ? {
            id: user.id,
            name: user.name || null,
            phone: user.id?.split(':')[0]?.split('@')[0] || null,
        } : null,
    });
});

/**
 * GET /qr - Get QR code as text
 */
app.get('/qr', (req, res) => {
    if (connectionState === 'connected') {
        return res.status(200).json({
            message: 'Already connected',
            connected: true
        });
    }

    if (!qrCode) {
        return res.status(404).json({
            error: 'No QR code available',
            status: connectionState
        });
    }

    res.json({ qr: qrCode });
});

/**
 * GET /qr/image - Get QR code as PNG image
 */
app.get('/qr/image', async (req, res) => {
    if (connectionState === 'connected') {
        return res.status(200).send('Already connected');
    }

    if (!qrCode) {
        return res.status(404).send('No QR code available');
    }

    try {
        const qrImage = await qrcode.toBuffer(qrCode, { type: 'png', width: 300 });
        res.type('png').send(qrImage);
    } catch (error) {
        res.status(500).json({ error: 'Failed to generate QR image' });
    }
});

/**
 * POST /send - Send a message
 * Body: { to: "1234567890", message: "Hello!" }
 */
app.post('/send', async (req, res) => {
    const { to, message, chatId } = req.body;

    // Support both 'to' (phone number) and 'chatId' (full JID)
    let recipient = chatId;
    if (!recipient && to) {
        // Convert phone number to JID
        recipient = to.replace(/[^0-9]/g, '') + '@s.whatsapp.net';
    }

    if (!recipient || !message) {
        return res.status(400).json({
            error: 'Missing required fields: to/chatId and message'
        });
    }

    if (connectionState !== 'connected' || !sock) {
        return res.status(503).json({
            error: 'WhatsApp not connected',
            status: connectionState
        });
    }

    // Verify socket is actually alive
    if (!sock.user) {
        logger.warn('[SEND] Socket exists but no user - connection may be stale');
        return res.status(503).json({
            error: 'WhatsApp connection stale - reconnecting',
            status: 'stale'
        });
    }

    try {
        logger.info(`[SEND] Attempting to send to ${recipient}: "${message.substring(0, 50)}..."`);
        const result = await sock.sendMessage(recipient, { text: message });
        logger.info(`[SEND] Success! MessageId: ${result?.key?.id || 'unknown'}`);
        res.json({ success: true, to: recipient, messageId: result?.key?.id });
    } catch (error) {
        logger.error('[SEND] Failed:', error);
        res.status(500).json({ error: error.message, stack: error.stack });
    }
});

/**
 * POST /webhook - Configure webhook URL
 * Body: { url: "http://localhost:3978/whatsapp/webhook" }
 */
app.post('/webhook', (req, res) => {
    const { url } = req.body;

    if (!url) {
        return res.status(400).json({ error: 'Missing webhook URL' });
    }

    webhookUrl = url;
    logger.info(`Webhook configured: ${url}`);
    res.json({ success: true, webhookUrl: url });
});

/**
 * GET /webhook - Get current webhook URL
 */
app.get('/webhook', (req, res) => {
    res.json({ webhookUrl: webhookUrl || null });
});

/**
 * POST /disconnect - Disconnect from WhatsApp
 */
app.post('/disconnect', async (req, res) => {
    const { logout } = req.body;

    if (!sock) {
        return res.json({ success: true, message: 'Already disconnected' });
    }

    try {
        if (logout) {
            await sock.logout();
            // Clear auth
            if (fs.existsSync(AUTH_DIR)) {
                fs.rmSync(AUTH_DIR, { recursive: true, force: true });
            }
        } else {
            await sock.end();
        }

        sock = null;
        connectionState = 'disconnected';
        qrCode = null;

        res.json({ success: true, loggedOut: !!logout });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

/**
 * POST /reconnect - Reconnect to WhatsApp
 */
app.post('/reconnect', async (req, res) => {
    if (connectionState === 'connected') {
        return res.json({ success: true, message: 'Already connected' });
    }

    connectionState = 'connecting';
    connectWhatsApp();

    res.json({ success: true, message: 'Reconnecting...' });
});

/**
 * Health check
 */
app.get('/health', (req, res) => {
    res.json({
        ok: true,
        service: 'whatsapp-service',
        uptime: process.uptime()
    });
});

// ==================== Start Server ====================

app.listen(PORT, () => {
    console.log('='.repeat(60));
    console.log('  WhatsApp Service (Baileys)');
    console.log('='.repeat(60));
    console.log(`  API running on: http://localhost:${PORT}`);
    console.log(`  Auth directory: ${AUTH_DIR}`);
    console.log('='.repeat(60));
    console.log('');
    console.log('Endpoints:');
    console.log('  GET  /status      - Connection status');
    console.log('  GET  /qr          - Get QR code text');
    console.log('  GET  /qr/image    - Get QR code as PNG');
    console.log('  POST /send        - Send message');
    console.log('  POST /webhook     - Set webhook URL');
    console.log('  POST /disconnect  - Disconnect');
    console.log('  POST /reconnect   - Reconnect');
    console.log('');
    console.log('='.repeat(60));
    console.log('');

    // Start WhatsApp connection
    connectWhatsApp();
});

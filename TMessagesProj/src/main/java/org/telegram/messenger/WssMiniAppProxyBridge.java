package org.telegram.messenger;

import android.text.TextUtils;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Arrays;

import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

public class WssMiniAppProxyBridge {
    private static final int BUFFER_SIZE = 16 * 1024;
    private static final int MAX_FRAME_SIZE = 2 * 1024 * 1024;
    private static final SecureRandom secureRandom = new SecureRandom();
    private static final Object lock = new Object();

    private static ServerSocket serverSocket;
    private static Thread acceptThread;
    private static volatile boolean running;
    private static String currentHost = "";
    private static int currentPort;
    private static String currentPath = "";
    private static int localPort;

    public static boolean shouldUseFromSettings() {
        return SharedConfig.wssUseForMiniApps
                && SharedConfig.wssTransportMode == SharedConfig.TRANSPORT_WSS_SOCKS5
                && !TextUtils.isEmpty(SharedConfig.wssHost);
    }

    public static boolean isRunning() {
        return running;
    }

    public static int ensureStarted() {
        synchronized (lock) {
            if (!shouldUseFromSettings()) {
                stopLocked();
                return 0;
            }
            String host = SharedConfig.wssHost.trim();
            int port = SharedConfig.wssPort > 0 ? SharedConfig.wssPort : 443;
            String path = SharedConfig.normalizeWssPath(SharedConfig.wssPath);
            if (running && serverSocket != null && TextUtils.equals(host, currentHost) && port == currentPort && TextUtils.equals(path, currentPath)) {
                return localPort;
            }
            stopLocked();
            try {
                serverSocket = new ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"));
                localPort = serverSocket.getLocalPort();
                currentHost = host;
                currentPort = port;
                currentPath = path;
                running = true;
                ServerSocket socket = serverSocket;
                acceptThread = new Thread(() -> acceptLoop(socket), "WssMiniAppProxyBridge");
                acceptThread.setDaemon(true);
                acceptThread.start();
                if (BuildVars.LOGS_ENABLED) {
                    FileLog.d("wss_miniapp bridge_started local_port=" + localPort + " gateway=" + currentHost + ":" + currentPort + currentPath);
                }
                return localPort;
            } catch (Exception e) {
                FileLog.e(e);
                stopLocked();
                return 0;
            }
        }
    }

    public static void stop() {
        synchronized (lock) {
            stopLocked();
        }
    }

    private static void stopLocked() {
        running = false;
        closeQuietly(serverSocket);
        serverSocket = null;
        acceptThread = null;
        localPort = 0;
    }

    private static void acceptLoop(ServerSocket socket) {
        while (running && socket == serverSocket) {
            try {
                Socket client = socket.accept();
                client.setTcpNoDelay(true);
                String host = currentHost;
                int port = currentPort;
                String path = currentPath;
                Thread thread = new Thread(() -> handleClient(client, host, port, path), "WssMiniAppProxySession");
                thread.setDaemon(true);
                thread.start();
            } catch (IOException e) {
                if (running) {
                    FileLog.e(e);
                }
            }
        }
    }

    private static void handleClient(Socket client, String gatewayHost, int gatewayPort, String gatewayPath) {
        SSLSocket remote = null;
        try {
            client.setSoTimeout(30000);
            SocksTarget target = readLocalSocksConnect(client);
            remote = (SSLSocket) SSLSocketFactory.getDefault().createSocket(gatewayHost, gatewayPort);
            remote.setUseClientMode(true);
            remote.setTcpNoDelay(true);
            remote.setSoTimeout(30000);
            remote.startHandshake();

            InputStream remoteIn = remote.getInputStream();
            OutputStream remoteOut = remote.getOutputStream();
            doWebSocketUpgrade(remoteIn, remoteOut, gatewayHost, gatewayPort, gatewayPath);
            writeWebSocketFrame(remoteOut, new byte[]{0x05, 0x01, 0x00});
            byte[] authResponse = readWebSocketPayload(remoteIn, remoteOut);
            if (authResponse == null || authResponse.length < 2 || authResponse[0] != 0x05 || authResponse[1] != 0x00) {
                throw new IOException("wss miniapp socks auth failed");
            }
            writeWebSocketFrame(remoteOut, buildSocksConnect(target.host, target.port));
            byte[] connectResponse = readWebSocketPayload(remoteIn, remoteOut);
            if (connectResponse == null || connectResponse.length < 2 || connectResponse[0] != 0x05 || connectResponse[1] != 0x00) {
                throw new IOException("wss miniapp socks connect failed");
            }
            writeLocalSocksSuccess(client.getOutputStream());
            client.setSoTimeout(0);
            remote.setSoTimeout(0);
            bridge(client, remote, remoteIn, remoteOut);
        } catch (Exception e) {
            if (BuildVars.LOGS_ENABLED) {
                FileLog.e(e);
            }
        } finally {
            closeQuietly(client);
            closeQuietly(remote);
        }
    }

    private static SocksTarget readLocalSocksConnect(Socket client) throws IOException {
        InputStream in = client.getInputStream();
        OutputStream out = client.getOutputStream();
        int version = readByte(in);
        int methodsCount = readByte(in);
        if (version != 0x05 || methodsCount <= 0) {
            throw new IOException("bad socks greeting");
        }
        byte[] methods = readFully(in, methodsCount);
        boolean supportsNoAuth = false;
        for (byte method : methods) {
            if ((method & 0xff) == 0x00) {
                supportsNoAuth = true;
                break;
            }
        }
        out.write(new byte[]{0x05, supportsNoAuth ? (byte) 0x00 : (byte) 0xff});
        out.flush();
        if (!supportsNoAuth) {
            throw new IOException("socks no-auth method unsupported by client");
        }

        int requestVersion = readByte(in);
        int command = readByte(in);
        readByte(in);
        int addressType = readByte(in);
        if (requestVersion != 0x05 || command != 0x01) {
            writeLocalSocksFailure(out);
            throw new IOException("only socks connect is supported");
        }
        String host;
        if (addressType == 0x01) {
            host = InetAddress.getByAddress(readFully(in, 4)).getHostAddress();
        } else if (addressType == 0x04) {
            host = InetAddress.getByAddress(readFully(in, 16)).getHostAddress();
        } else if (addressType == 0x03) {
            int length = readByte(in);
            host = new String(readFully(in, length), StandardCharsets.UTF_8);
        } else {
            writeLocalSocksFailure(out);
            throw new IOException("bad socks address type");
        }
        int port = (readByte(in) << 8) | readByte(in);
        return new SocksTarget(host, port);
    }

    private static void doWebSocketUpgrade(InputStream in, OutputStream out, String host, int port, String path) throws IOException {
        byte[] keyBytes = new byte[16];
        secureRandom.nextBytes(keyBytes);
        String key = Base64.encodeToString(keyBytes, Base64.NO_WRAP);
        String hostHeader = port == 443 ? host : host + ":" + port;
        String normalizedPath = SharedConfig.normalizeWssPath(path);
        String request =
                "GET " + normalizedPath + " HTTP/1.1\r\n" +
                        "Host: " + hostHeader + "\r\n" +
                        "Upgrade: websocket\r\n" +
                        "Connection: Upgrade\r\n" +
                        "Sec-WebSocket-Key: " + key + "\r\n" +
                        "Sec-WebSocket-Version: 13\r\n" +
                        "Sec-WebSocket-Protocol: binary\r\n" +
                        "Origin: https://web.telegram.org\r\n" +
                        "User-Agent: Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36\r\n" +
                        "\r\n";
        out.write(request.getBytes(StandardCharsets.ISO_8859_1));
        out.flush();

        ByteArrayOutputStream header = new ByteArrayOutputStream();
        int matched = 0;
        byte[] delimiter = new byte[]{'\r', '\n', '\r', '\n'};
        while (matched < delimiter.length) {
            int value = in.read();
            if (value < 0) {
                throw new IOException("wss http eof");
            }
            header.write(value);
            matched = value == delimiter[matched] ? matched + 1 : (value == delimiter[0] ? 1 : 0);
            if (header.size() > 32 * 1024) {
                throw new IOException("wss http response too large");
            }
        }
        String response = header.toString("ISO-8859-1");
        if (!response.startsWith("HTTP/1.1 101") && !response.startsWith("HTTP/1.0 101")) {
            throw new IOException("wss http upgrade failed");
        }
    }

    private static byte[] buildSocksConnect(String host, int port) throws IOException {
        ByteArrayOutputStream request = new ByteArrayOutputStream();
        request.write(0x05);
        request.write(0x01);
        request.write(0x00);
        byte[] address = host.getBytes(StandardCharsets.UTF_8);
        if (address.length > 255) {
            throw new IOException("socks host too long");
        }
        request.write(0x03);
        request.write(address.length);
        request.write(address);
        request.write((port >> 8) & 0xff);
        request.write(port & 0xff);
        return request.toByteArray();
    }

    private static void bridge(Socket client, SSLSocket remote, InputStream remoteIn, OutputStream remoteOut) throws IOException {
        InputStream clientIn = client.getInputStream();
        OutputStream clientOut = client.getOutputStream();
        Thread upload = new Thread(() -> {
            byte[] buffer = new byte[BUFFER_SIZE];
            try {
                while (running) {
                    int read = clientIn.read(buffer);
                    if (read < 0) {
                        break;
                    }
                    writeWebSocketFrame(remoteOut, Arrays.copyOf(buffer, read));
                }
            } catch (Exception ignore) {
            } finally {
                closeQuietly(client);
                closeQuietly(remote);
            }
        }, "WssMiniAppProxyUpload");
        upload.setDaemon(true);
        upload.start();

        while (running) {
            byte[] payload = readWebSocketPayload(remoteIn, remoteOut);
            if (payload == null) {
                break;
            }
            clientOut.write(payload);
            clientOut.flush();
        }
    }

    private static void writeLocalSocksSuccess(OutputStream out) throws IOException {
        out.write(new byte[]{0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0});
        out.flush();
    }

    private static void writeLocalSocksFailure(OutputStream out) throws IOException {
        out.write(new byte[]{0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0});
        out.flush();
    }

    private static byte[] readWebSocketPayload(InputStream in, OutputStream out) throws IOException {
        while (true) {
            int first = in.read();
            if (first < 0) {
                return null;
            }
            int second = readByte(in);
            int opcode = first & 0x0f;
            boolean masked = (second & 0x80) != 0;
            long length = second & 0x7f;
            if (length == 126) {
                length = (readByte(in) << 8) | readByte(in);
            } else if (length == 127) {
                length = 0;
                for (int i = 0; i < 8; i++) {
                    length = (length << 8) | readByte(in);
                }
            }
            if (length < 0 || length > MAX_FRAME_SIZE) {
                throw new IOException("wss frame too large");
            }
            byte[] mask = masked ? readFully(in, 4) : null;
            byte[] payload = readFully(in, (int) length);
            if (masked) {
                for (int i = 0; i < payload.length; i++) {
                    payload[i] ^= mask[i % 4];
                }
            }
            if (opcode == 0x8) {
                return null;
            } else if (opcode == 0x9) {
                writeWebSocketFrame(out, payload, 0xA);
            } else if (opcode == 0x1 || opcode == 0x2 || opcode == 0x0) {
                return payload;
            }
        }
    }

    private static void writeWebSocketFrame(OutputStream out, byte[] payload) throws IOException {
        writeWebSocketFrame(out, payload, 0x2);
    }

    private static void writeWebSocketFrame(OutputStream out, byte[] payload, int opcode) throws IOException {
        synchronized (out) {
            int size = payload.length;
            ByteArrayOutputStream frame = new ByteArrayOutputStream(size + 14);
            frame.write(0x80 | opcode);
            if (size < 126) {
                frame.write(0x80 | size);
            } else if (size <= 0xffff) {
                frame.write(0x80 | 126);
                frame.write((size >> 8) & 0xff);
                frame.write(size & 0xff);
            } else {
                frame.write(0x80 | 127);
                for (int i = 7; i >= 0; i--) {
                    frame.write((int) ((((long) size) >> (8 * i)) & 0xff));
                }
            }
            byte[] mask = new byte[4];
            secureRandom.nextBytes(mask);
            frame.write(mask);
            for (int i = 0; i < size; i++) {
                frame.write(payload[i] ^ mask[i % 4]);
            }
            out.write(frame.toByteArray());
            out.flush();
        }
    }

    private static int readByte(InputStream in) throws IOException {
        int value = in.read();
        if (value < 0) {
            throw new IOException("unexpected eof");
        }
        return value;
    }

    private static byte[] readFully(InputStream in, int size) throws IOException {
        byte[] data = new byte[size];
        int offset = 0;
        while (offset < size) {
            int read = in.read(data, offset, size - offset);
            if (read < 0) {
                throw new IOException("unexpected eof");
            }
            offset += read;
        }
        return data;
    }

    private static void closeQuietly(Closeable closeable) {
        if (closeable == null) {
            return;
        }
        try {
            closeable.close();
        } catch (Exception ignore) {
        }
    }

    private static final class SocksTarget {
        final String host;
        final int port;

        SocksTarget(String host, int port) {
            this.host = host;
            this.port = port;
        }
    }
}

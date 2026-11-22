'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');
const { Worker } = require('worker_threads');

assert(os.hostname().length > 0);
assert(Number.isFinite(Date.now()));

// Check lookups with Latin-1 text coming from both byte and UTF-16 input.
// Include lengths around the hash reader's 4- and 8-byte boundaries.
for (let length = 1; length <= 128; length++) {
  const bytes = Buffer.alloc(length);
  for (let i = 0; i < length; i++) bytes[i] = (i * 73 + length) & 0xff;
  const latin1 = bytes.toString('latin1');
  const utf16 = Buffer.from(latin1, 'utf16le').toString('utf16le');
  const map = new Map([[latin1, length]]);
  assert.strictEqual(map.get(utf16), length);
  assert.strictEqual(new Map([[utf16, length]]).get(latin1), length);
}

assert.strictEqual(
  crypto.createHash('sha256').update('abc').digest('hex'),
  'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
);

// A small WebAssembly module exporting add(i32, i32).
const wasm = new WebAssembly.Module(Uint8Array.from([
  0, 97, 115, 109, 1, 0, 0, 0, 1, 7, 1, 96, 2, 127, 127, 1, 127,
  3, 2, 1, 0, 7, 7, 1, 3, 97, 100, 100, 0, 0,
  10, 9, 1, 7, 0, 32, 0, 32, 1, 106, 11,
]));
assert.strictEqual(new WebAssembly.Instance(wasm).exports.add(19, 23), 42);

const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'node-legacy-smoke-'));
try {
  const file = path.join(directory, 'data');
  fs.writeFileSync(file, 'legacy');
  assert.strictEqual(fs.readFileSync(file, 'utf8'), 'legacy');
} finally {
  fs.rmSync(directory, { recursive: true, force: true });
}

let workerDone = false;
let networkDone = false;
const timeout = setTimeout(() => {
  throw new Error('Legacy smoke test timed out');
}, 30000);
function finish() {
  if (workerDone && networkDone) {
    clearTimeout(timeout);
    console.log('Legacy smoke test passed');
  }
}

const worker = new Worker(
  "require('worker_threads').parentPort.postMessage(6 * 7)",
  { eval: true },
);
let received = false;
worker.once('message', (message) => {
  assert.strictEqual(message, 42);
  received = true;
});
worker.once('exit', (code) => {
  assert.strictEqual(code, 0);
  assert(received);
  workerDone = true;
  finish();
});

const server = net.createServer((socket) => socket.end('pong'));
server.listen(0, '127.0.0.1', () => {
  const client = net.connect(server.address().port, '127.0.0.1');
  let response = '';
  client.setEncoding('utf8');
  client.on('data', (chunk) => { response += chunk; });
  client.on('end', () => {
    assert.strictEqual(response, 'pong');
    server.close(() => {
      networkDone = true;
      finish();
    });
  });
});

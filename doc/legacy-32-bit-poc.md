# Experimental 32-bit port

This is work in progress, not a supported Node.js distribution. The targets
are Linux x86, Windows 7 SP1 and later on x86, and Android 7 (API 24) and later
on ARMv7, including an Android executable and embedded shared library. **No
workflow or target build has yet been validated on the requested legacy OSes.**

## GitHub Actions builds

The experimental Linux x86, Windows x86 and Android ARMv7 workflows can be
run manually with `workflow_dispatch`; they also run for relevant changes on
`arena/**` branches. They produce short-lived artifacts only after successful
build and inspection steps. They use pinned runner families, GCC major version,
Android NDK version and action revisions, but not fully pinned OS packages or
MSVC patch versions: they are not bit-for-bit reproducible toolchains.

`Experimental legacy GitHub release` is a separate manual workflow. First,
make the workflow available on the repository's default branch (GitHub requires
this for manual dispatch), then create a `legacy-*` Git tag in the fork pointing
to the exact commit to build and select that same commit or branch when
dispatching the workflow. The tag
must contain only letters, digits, dots, underscores and hyphens after `legacy-`.
The workflow runs the tool tests and all three build workflows (four artifacts),
then verifies their checksums and publishes four archives and a SHA256SUMS file
as an **experimental prerelease**. It refuses to publish to `nodejs/node`, and
will fail rather than replace an existing release. It needs Actions permission
to write repository contents. Normal push and standalone build runs do not
publish releases. Build and inspection success is not proof of Windows 7 or
Android device compatibility; neither target has been runtime-tested here.

The first builds explicitly disable Temporal to avoid introducing a 32-bit Rust
toolchain dependency. Android and Windows also disable OpenSSL assembly. These
are temporary feature or performance limitations, not claims of parity with
release builds. IA-32 V8 requires at least SSE2 and CMOV. Linux executables
built on Ubuntu 24.04 may require newer glibc than older Linux installations;
check the recorded ELF version requirements and test against the intended
minimum userspace before claiming compatibility.

A separate local x86-musl build uses Zig/Clang and disables OpenSSL assembly
and single-executable application support as well as Temporal. Its toolchain
needed a local compiler-runtime `__atomic_is_lock_free` workaround. It is not
the GCC/glibc Actions build, and its result cannot validate that workflow.

The Linux and Windows workflows run a small JavaScript smoke test. Each artifact
includes `smoke.js`: run it with the accompanying executable to repeat those
checks on a target system, for example `node.exe smoke.js` on Windows. Android
may need `TMPDIR` set to a writable directory; the shared library also needs a
separate embedding test; its artifact also includes the Node public headers.
The Windows workflow reports normal and delay PE
imports and rejects a direct import of
`GetSystemTimePreciseAsFileTime`. Import inspection does not cover dynamically
resolved APIs or other DLLs, and **does not establish Windows 7 compatibility**.
The Android workflow inspects ELF metadata; it does not execute Android code.

The V8 string-hasher regression test in `deps/v8/test/unittests/strings` checks
that hashes of Latin-1 and corresponding UTF-16 values match over a range of
offsets and lengths. It is registered with V8's GN unit-test target; the Node
GitHub Actions smoke tests do **not** run that V8 GN target. A separate local
IA-32 harness linked the actual modified V8 hasher and passed 1,028 parity cases
on an x86-64 Linux host; this does not validate a complete Node build.

## Windows compatibility notes

The IA-32 startup guard permits Windows 7 SP1 as an experimental target. Libuv
looks up the precise Windows clock dynamically and falls back to the older,
lower-resolution clock when unavailable. On systems without `GetHostNameW`,
the hostname fallback uses `GetComputerNameExW`; unlike `GetHostNameW`, it
does not consult Winsock namespace providers. These fallbacks have not yet
been exercised on Windows 7. The compiler runtime, all transitive DLLs, dynamic
API lookups and behavior of dependencies still require auditing and testing.

## Android build notes

`./android-configure <ndk> 24 arm [configure options...]` separates target
and host compilers and propagates configuration errors. On an x86-64 Linux
host it defaults to 32-bit host compilers for ARM and IA-32, so a multilib C/C++
toolchain is required. Pass `--shared` for the shared build. The Android NDK
path must not contain whitespace because the GYP Android Makefile generator
does not handle spaces reliably. The Android trap-handler patch is not applied
automatically. Build and runtime compatibility, including embedded lifecycle,
have not yet been established.

## Remaining work

- Run the three workflows, fix build failures, and expand tests to include native
  addons, workers, networking, TLS, WebAssembly and dates beyond 2038. Test a
  sufficiently old Linux userspace separately.
- Audit Windows imports and runtime dependencies, then test on a real Windows 7
  SP1 system as well as newer Windows.
- Test Android executable and shared-library builds on Android 7 and later,
  including shell execution, embedded-app lifecycle, JIT, packaging and loading.
- Preserve coverage of existing supported 64-bit targets and evaluate the
  performance and security implications of 32-bit builds. Windows 7 is
  end-of-life; this port cannot provide operating-system security updates.

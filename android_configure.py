import os
import platform
import shlex
import shutil
import subprocess
import sys


# Kept as an explicit opt-in for existing users; it is not part of a normal
# Android build and has not been validated for this port.
def patch_android():
    print('- Patches List -')
    print('[1] [deps/v8/src/trap-handler/trap-handler.h] related to https://github.com/nodejs/node/issues/36287')
    if platform.system() == 'Linux':
        with open('./android-patches/trap-handler.h.patch', 'rb') as patch:
            subprocess.run(['patch', '-f', './deps/v8/src/trap-handler/trap-handler.h'],
                           stdin=patch, check=True)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    system = platform.system()
    if system not in ('Linux', 'Darwin'):
        print('android-configure is currently only supported on Linux and Darwin.', file=sys.stderr)
        return 1
    if args == ['patch']:
        patch_android()
        return 0
    if len(args) < 3:
        print('Usage: ./android-configure <path to the Android NDK> <Android API level> '
              '<target architecture> [configure options...]', file=sys.stderr)
        return 1

    ndk_path, api, arch = args[:3]
    ndk_path = os.path.abspath(ndk_path)
    if not os.path.isdir(ndk_path) or not os.listdir(ndk_path):
        print('Error: Invalid path to the Android NDK', file=sys.stderr)
        return 1
    # GYP's Android Makefile generator cannot safely handle spaces in paths.
    if any(char.isspace() for char in ndk_path):
        print('Error: Android NDK path must not contain whitespace', file=sys.stderr)
        return 1
    if not api.isdecimal() or int(api) < 24:
        print('Error: Android API level must be an integer of at least 24 (Android 7.0)',
              file=sys.stderr)
        return 1

    targets = {
        'arm': ('arm', 'armv7a-linux-androideabi'),
        'arm64': ('arm64', 'aarch64-linux-android'),
        'aarch64': ('arm64', 'aarch64-linux-android'),
        'x86': ('ia32', 'i686-linux-android'),
        'x86_64': ('x64', 'x86_64-linux-android'),
    }
    if arch not in targets:
        print('Error: target architecture must be one of: ' + ', '.join(targets),
              file=sys.stderr)
        return 1
    dest_cpu, prefix = targets[arch]
    host_os = 'darwin' if system == 'Darwin' else 'linux'
    bin_dir = os.path.join(ndk_path, 'toolchains', 'llvm', 'prebuilt',
                           host_os + '-x86_64', 'bin')
    target_cc = os.path.join(bin_dir, prefix + api + '-clang')
    target_cxx = target_cc + '++'
    llvm_ar = os.path.join(bin_dir, 'llvm-ar')
    for executable in (target_cc, target_cxx, llvm_ar):
        if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
            print('Error: NDK tool not found or not executable: ' + executable,
                  file=sys.stderr)
            return 1

    env = os.environ.copy()
    env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')
    # configure.py examines CC/CXX for the target; GYP distinguishes host and
    # target tools. Callers may explicitly override either toolset.
    env['CC_target'] = env.get('CC_target') or target_cc
    env['CXX_target'] = env.get('CXX_target') or target_cxx
    env['CC'] = env['CC_target']
    env['CXX'] = env['CXX_target']
    host_cc = shutil.which('cc') or 'cc'
    host_cxx = shutil.which('c++') or 'c++'
    # The ARM and IA-32 V8 snapshot generators need 32-bit host tools.
    # Linux x86-64 hosts can supply these with their multilib toolchain.
    if system == 'Linux' and platform.machine() in ('x86_64', 'amd64') and dest_cpu in ('arm', 'ia32'):
        host_cc += ' -m32'
        host_cxx += ' -m32'
    env['CC_host'] = env.get('CC_host') or host_cc
    env['CXX_host'] = env.get('CXX_host') or host_cxx
    env['AR_target'] = env.get('AR_target') or llvm_ar
    env['LINK_target'] = env.get('LINK_target') or env['CXX_target']
    defines = {
        'target_arch': dest_cpu,
        'v8_target_arch': dest_cpu,
        'android_target_arch': dest_cpu,
        'host_os': host_os,
        'OS': 'android',
        'android_ndk_path': ndk_path,
    }
    env['GYP_DEFINES'] = ' '.join(
        shlex.quote(key + '=' + value) for key, value in defines.items())
    command = ['./configure', '--dest-cpu=' + dest_cpu, '--dest-os=android',
               '--openssl-no-asm', '--cross-compiling', *args[3:]]
    print('Configuring Android ' + dest_cpu + ' for API ' + api + '...', flush=True)
    try:
        return subprocess.run(command, env=env, check=False).returncode
    except OSError as exc:
        print('Error executing configure: ' + str(exc), file=sys.stderr)
        return 1

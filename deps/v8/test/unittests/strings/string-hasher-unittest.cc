// Copyright 2026 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "src/strings/string-hasher-inl.h"
#include "testing/gtest/include/gtest/gtest.h"

namespace v8 {
namespace internal {

TEST(StringHasherTest, Latin1AndTwoByteHashesMatch) {
  constexpr uint64_t secret[] = {0x2d358dccaa6c78a5ULL, 0x8bb84b93962eacc9ULL,
                                 0x4b33a62ed433d4a3ULL};
  constexpr uint64_t seed = 0x123456789abcdef0ULL;
  uint8_t latin1[260];
  uint16_t two_byte[260];
  for (unsigned i = 0; i < 260; ++i) {
    // Exercise zero bytes and characters above ASCII as well as ASCII.
    latin1[i] = static_cast<uint8_t>(i * 73);
    two_byte[i] = latin1[i];
  }

  for (unsigned offset = 0; offset < 4; ++offset) {
    for (unsigned length = 0; length <= 256; ++length) {
      SCOPED_TRACE(::testing::Message() << "offset=" << offset
                                        << " length=" << length);
      EXPECT_EQ(rapidhash(latin1 + offset, length, seed, secret),
                detail::HashConvertingTo8Bit(two_byte + offset, length, seed,
                                             secret));
    }
  }
}

}  // namespace internal
}  // namespace v8

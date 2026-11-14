package main

import (
	"io"
	"net"
	"testing"
	"time"
)

// Decisao 159: countingConn's record-aware read limiter must deliver
// the EXACT same `in` byte count for the handshake-only portion of a
// stream, no matter how the underlying transport happens to fragment
// its Read() returns -- 1 byte at a time, everything at once, split
// exactly at a TLS record boundary, or split 1 byte off from that
// boundary in either direction. And it must NEVER let a byte belonging
// to the record AFTER the handshake (here: a synthetic "application
// data" record standing in for the client's first post-handshake HTTP
// write) leak into that count while framing is active.

// fakeChunkedConn is a net.Conn backed by a fixed byte slice, never
// returning more than chunkSize bytes per Read() call (and never more
// than the caller's own buffer length -- same net.Conn.Read contract
// countingConn's whole fix leans on).
type fakeChunkedConn struct {
	data      []byte
	pos       int
	chunkSize int
}

func (f *fakeChunkedConn) Read(b []byte) (int, error) {
	if f.pos >= len(f.data) {
		return 0, io.EOF
	}
	n := len(b)
	if n > f.chunkSize {
		n = f.chunkSize
	}
	if remaining := len(f.data) - f.pos; n > remaining {
		n = remaining
	}
	if n == 0 {
		return 0, nil
	}
	copy(b[:n], f.data[f.pos:f.pos+n])
	f.pos += n
	return n, nil
}

func (f *fakeChunkedConn) Write(b []byte) (int, error)        { return len(b), nil }
func (f *fakeChunkedConn) Close() error                       { return nil }
func (f *fakeChunkedConn) LocalAddr() net.Addr                { return nil }
func (f *fakeChunkedConn) RemoteAddr() net.Addr                { return nil }
func (f *fakeChunkedConn) SetDeadline(t time.Time) error      { return nil }
func (f *fakeChunkedConn) SetReadDeadline(t time.Time) error  { return nil }
func (f *fakeChunkedConn) SetWriteDeadline(t time.Time) error { return nil }

// buildRecord returns a synthetic TLS record: 5-byte header (an
// arbitrary content type, legacy version 0x0303, big-endian length)
// followed by `length` filler bytes. Byte-for-byte shape is all that
// matters here -- countingConn's framing logic never looks past the
// header's length field.
func buildRecord(contentType byte, length int, fill byte) []byte {
	rec := make([]byte, tlsRecordHeaderLen+length)
	rec[0] = contentType
	rec[1], rec[2] = 0x03, 0x03
	rec[3] = byte(length >> 8)
	rec[4] = byte(length)
	for i := 0; i < length; i++ {
		rec[tlsRecordHeaderLen+i] = fill
	}
	return rec
}

// readExactlyFramed drives cc.Read() in a loop with a buffer
// deliberately LARGER than any single record (mimicking crypto/tls's
// own inflated read buffer, `needs+bytes.MinRead`) until exactly n
// bytes have been consumed -- the scenario that leaked bytes from the
// next record into the handshake's tally before Decisao 159.
func readExactlyFramed(t *testing.T, cc *countingConn, n int) []byte {
	t.Helper()
	out := make([]byte, 0, n)
	buf := make([]byte, 4096) // >> any record used in these tests, on purpose
	for len(out) < n {
		readN, err := cc.Read(buf)
		if readN > 0 {
			out = append(out, buf[:readN]...)
		}
		if err != nil && err != io.EOF {
			t.Fatalf("unexpected error reading framed stream: %v", err)
		}
		if readN == 0 && err == io.EOF {
			t.Fatalf("stream exhausted after %d/%d bytes", len(out), n)
		}
	}
	if len(out) != n {
		t.Fatalf("over-read: wanted exactly %d bytes, got %d", n, len(out))
	}
	return out
}

func TestCountingConnRecordFraming_MatchesAcrossFragmentations(t *testing.T) {
	record1 := buildRecord(0x16, 50, 0xAA) // ServerHello-ish
	record2 := buildRecord(0x17, 36, 0xBB) // Finished-ish (TLS1.3 wraps it as "application_data" at the record layer too)
	appData := buildRecord(0x17, 71, 0xCC) // the client's first post-handshake HTTP write -- must NEVER be counted while framing is active

	handshakeLen := len(record1) + len(record2)
	stream := append(append(append([]byte{}, record1...), record2...), appData...)

	boundary := len(record1) // first intra-handshake record boundary
	handshakeEnd := handshakeLen // the boundary that actually matters: handshake vs. post-handshake data

	chunkSizes := map[string]int{
		"one_byte_at_a_time":          1,
		"all_at_once":                 len(stream) + 1000,
		"at_first_record_boundary":    boundary,
		"first_record_boundary_plus1": boundary + 1,
		"first_record_boundary_minus1": boundary - 1,
		"at_handshake_end_boundary":    handshakeEnd,
		"handshake_end_boundary_plus1": handshakeEnd + 1,
		"handshake_end_boundary_minus1": handshakeEnd - 1,
	}

	var results []int64
	for name, chunkSize := range chunkSizes {
		t.Run(name, func(t *testing.T) {
			raw := &fakeChunkedConn{data: append([]byte{}, stream...), chunkSize: chunkSize}
			cc := newCountingConn(raw)

			got := readExactlyFramed(t, cc, handshakeLen)
			if string(got) != string(stream[:handshakeLen]) {
				t.Fatalf("framed read returned wrong bytes for chunkSize=%d", chunkSize)
			}

			inAfterHandshake, _ := cc.snapshot()
			if inAfterHandshake != int64(handshakeLen) {
				t.Fatalf("chunkSize=%d: in=%d, want exactly %d (no leak, no under-count)",
					chunkSize, inAfterHandshake, handshakeLen)
			}

			cc.disableRecordFraming()
			// post-handshake: now unrestricted passthrough, exactly like before Decisao 159
			rest := make([]byte, len(appData))
			if _, err := io.ReadFull(cc, rest); err != nil {
				t.Fatalf("chunkSize=%d: reading post-handshake data: %v", chunkSize, err)
			}
			if string(rest) != string(appData) {
				t.Fatalf("chunkSize=%d: post-handshake bytes corrupted", chunkSize)
			}

			results = append(results, inAfterHandshake)
		})
	}

	for i, r := range results {
		if r != int64(handshakeLen) {
			t.Fatalf("result[%d]=%d diverged from the expected %d -- fragmentation must never change the count", i, r, handshakeLen)
		}
	}
}

func TestCountingConnRecordFraming_ZeroLengthRecord(t *testing.T) {
	zeroRec := buildRecord(0x17, 0, 0x00)
	record2 := buildRecord(0x17, 10, 0xBB)
	stream := append(append([]byte{}, zeroRec...), record2...)

	raw := &fakeChunkedConn{data: stream, chunkSize: 4096}
	cc := newCountingConn(raw)

	got := readExactlyFramed(t, cc, len(stream))
	if string(got) != string(stream) {
		t.Fatalf("zero-length record handling corrupted the stream")
	}
	in, _ := cc.snapshot()
	if in != int64(len(stream)) {
		t.Fatalf("in=%d, want %d", in, len(stream))
	}
}

func TestCountingConnRecordFraming_WriteUnaffected(t *testing.T) {
	raw := &fakeChunkedConn{data: nil, chunkSize: 4096}
	cc := newCountingConn(raw)
	payload := []byte("anything, write is never record-aware")
	n, err := cc.Write(payload)
	if err != nil || n != len(payload) {
		t.Fatalf("Write: n=%d err=%v, want n=%d err=nil", n, err, len(payload))
	}
	_, out := cc.snapshot()
	if out != int64(len(payload)) {
		t.Fatalf("out=%d, want %d", out, len(payload))
	}
}

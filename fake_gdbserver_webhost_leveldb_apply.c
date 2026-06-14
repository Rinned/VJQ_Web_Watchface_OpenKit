#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 64
#define O_TRUNC 512

#define SRC "/home/owner/share/tmp/codex_vjq_000003_texture0.log"
#define DST "/home/owner/apps_rw/VJQAyUfd52/data/Local Storage/leveldb/000003.log"
#define LOG "/home/owner/share/tmp/codex_vjq_leveldb_apply.log"

static int g_log_fd = -1;

static long sc0(long nr) {
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0");
    __asm__ volatile ("svc 0" : "=r"(r0) : "r"(r7) : "memory");
    return r0;
}

static long sc1(long nr, long a) {
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    __asm__ volatile ("svc 0" : "+r"(r0) : "r"(r7) : "memory");
    return r0;
}

static long sc3(long nr, long a, long b, long c) {
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    __asm__ volatile ("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7) : "memory");
    return r0;
}

static unsigned long slen(const char *s) {
    unsigned long n = 0;
    while (s && s[n]) n++;
    return n;
}

static void log_s(const char *s) {
    if (s) {
        sc3(4, 1, (long)s, (long)slen(s));
        if (g_log_fd >= 0) sc3(4, g_log_fd, (long)s, (long)slen(s));
    }
}

static void log_int(long v) {
    unsigned long powers[] = {
        1000000000UL, 100000000UL, 10000000UL, 1000000UL, 100000UL,
        10000UL, 1000UL, 100UL, 10UL, 1UL
    };
    unsigned long x;
    int i;
    int started = 0;
    if (v < 0) {
        log_s("-");
        x = (unsigned long)(-v);
    } else {
        x = (unsigned long)v;
    }
    for (i = 0; i < 10; i++) {
        int digit = 0;
        while (x >= powers[i]) {
            x -= powers[i];
            digit++;
        }
        if (digit || started || powers[i] == 1UL) {
            char c[2];
            c[0] = (char)('0' + digit);
            c[1] = 0;
            log_s(c);
            started = 1;
        }
    }
}

static void dump_head(const char *path) {
    char buf[64];
    long fd = sc3(5, (long)path, O_RDONLY, 0);
    log_s("head ");
    log_s(path);
    log_s(" fd=");
    log_int(fd);
    if (fd >= 0) {
        long n = sc3(3, fd, (long)buf, sizeof(buf));
        log_s(" n=");
        log_int(n);
        sc1(6, fd);
    }
    log_s("\n");
}

void _start(void) {
    char buf[1024];
    long total = 0;
    long in, out;

    g_log_fd = (int)sc3(5, (long)LOG, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    log_s("fake_gdbserver_webhost_leveldb_apply start\n");
    log_s("pid=");
    log_int(sc0(20));
    log_s(" uid=");
    log_int(sc0(199));
    log_s("\n");
    dump_head("/proc/self/attr/current");
    dump_head(SRC);
    dump_head(DST);

    in = sc3(5, (long)SRC, O_RDONLY, 0);
    log_s("open src=");
    log_int(in);
    log_s("\n");
    if (in < 0) goto done;

    out = sc3(5, (long)DST, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    log_s("open dst=");
    log_int(out);
    log_s("\n");
    if (out < 0) {
        sc1(6, in);
        goto done;
    }

    for (;;) {
        long r = sc3(3, in, (long)buf, sizeof(buf));
        long w;
        if (r <= 0) break;
        w = sc3(4, out, (long)buf, r);
        log_s("chunk r=");
        log_int(r);
        log_s(" w=");
        log_int(w);
        log_s("\n");
        if (w < 0) break;
        total += w;
        if (w != r) break;
    }
    sc1(6, out);
    sc1(6, in);
    log_s("total=");
    log_int(total);
    log_s("\n");
    dump_head(DST);

done:
    log_s("fake_gdbserver_webhost_leveldb_apply end\n");
    if (g_log_fd >= 0) sc1(6, g_log_fd);
    sc1(1, 0);
}


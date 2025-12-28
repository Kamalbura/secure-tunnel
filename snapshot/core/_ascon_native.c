#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <limits.h>
#include <stdint.h>
#include <string.h>

#define ASCON_TAG_BYTES 16
#define ASCON_NONCE_BYTES 16
#define ASCON_KEY_BYTES 16

/*
 * Vendor includes: compile the CC0 Ascon C reference twice with different
 * symbol prefixes so both ascon128 (rate 8) and ascon128a (rate 16) variants
 * can coexist inside the same extension.
 */

#define ascon_loadkey ascon128_loadkey
#define ascon_initaead ascon128_initaead
#define ascon_adata ascon128_adata
#define ascon_encrypt ascon128_encrypt
#define ascon_decrypt ascon128_decrypt
#define ascon_final ascon128_final
#define ascon_gettag ascon128_gettag
#define ascon_verify ascon128_verify
#define ascon_aead_encrypt ascon128_ascon_aead_encrypt
#define ascon_aead_decrypt ascon128_ascon_aead_decrypt
#define crypto_aead_encrypt ascon128_crypto_aead_encrypt
#define crypto_aead_decrypt ascon128_crypto_aead_decrypt
#include "../third_party/ascon_c/asconaead128_opt64/aead.c"
#undef ascon_loadkey
#undef ascon_initaead
#undef ascon_adata
#undef ascon_encrypt
#undef ascon_decrypt
#undef ascon_final
#undef ascon_gettag
#undef ascon_verify
#undef ascon_aead_encrypt
#undef ascon_aead_decrypt
#undef crypto_aead_encrypt
#undef crypto_aead_decrypt

#define ascon_loadkey ascon128a_loadkey
#define ascon_initaead ascon128a_initaead
#define ascon_adata ascon128a_adata
#define ascon_encrypt ascon128a_encrypt
#define ascon_decrypt ascon128a_decrypt
#define ascon_final ascon128a_final
#define ascon_gettag ascon128a_gettag
#define ascon_verify ascon128a_verify
#define ascon_aead_encrypt ascon128a_ascon_aead_encrypt
#define ascon_aead_decrypt ascon128a_ascon_aead_decrypt
#define crypto_aead_encrypt ascon128a_crypto_aead_encrypt
#define crypto_aead_decrypt ascon128a_crypto_aead_decrypt
#include "../third_party/ascon_c/asconaead128a_opt64/aead.c"
#undef ascon_loadkey
#undef ascon_initaead
#undef ascon_adata
#undef ascon_encrypt
#undef ascon_decrypt
#undef ascon_final
#undef ascon_gettag
#undef ascon_verify
#undef ascon_aead_encrypt
#undef ascon_aead_decrypt
#undef crypto_aead_encrypt
#undef crypto_aead_decrypt

struct ascon_variant {
    const char *name;
    int (*encrypt_fn)(uint8_t *, uint8_t *, const uint8_t *, uint64_t,
                      const uint8_t *, uint64_t, const uint8_t *, const uint8_t *);
    int (*decrypt_fn)(uint8_t *, const uint8_t *, const uint8_t *, uint64_t,
                      const uint8_t *, uint64_t, const uint8_t *, const uint8_t *);
};

static const struct ascon_variant kVariants[] = {
    {"Ascon-AEAD128", ascon128_ascon_aead_encrypt, ascon128_ascon_aead_decrypt},
    {"Ascon-AEAD128a", ascon128a_ascon_aead_encrypt, ascon128a_ascon_aead_decrypt},
};

static const struct ascon_variant *resolve_variant(const char *name, Py_ssize_t name_len) {
    size_t i;
    for (i = 0; i < sizeof(kVariants) / sizeof(kVariants[0]); ++i) {
        const char *candidate = kVariants[i].name;
        size_t candidate_len = strlen(candidate);
        if ((Py_ssize_t)candidate_len != name_len) {
            continue;
        }
        if (memcmp(candidate, name, candidate_len) == 0) {
            return &kVariants[i];
        }
    }
    return NULL;
}

static int convert_length(Py_ssize_t value, uint64_t *dst, const char *field) {
    if (value < 0) {
        PyErr_Format(PyExc_ValueError, "%s length must be non-negative", field);
        return -1;
    }
    *dst = (uint64_t)value;
    return 0;
}

static int ensure_exact_length(const Py_buffer *view, Py_ssize_t required, const char *label) {
    if (view->len != required) {
        PyErr_Format(PyExc_ValueError, "%s must be %zd bytes", label, required);
        return -1;
    }
    return 0;
}

static int ensure_min_length(const Py_buffer *view, Py_ssize_t required, const char *label) {
    if (view->len < required) {
        PyErr_Format(PyExc_ValueError, "%s must be at least %zd bytes", label, required);
        return -1;
    }
    return 0;
}

static void release_buffers(Py_buffer *key, Py_buffer *nonce, Py_buffer *aad, Py_buffer *text) {
    if (key->buf != NULL) PyBuffer_Release(key);
    if (nonce->buf != NULL) PyBuffer_Release(nonce);
    if (aad->buf != NULL) PyBuffer_Release(aad);
    if (text->buf != NULL) PyBuffer_Release(text);
}

static PyObject *native_encrypt(PyObject *self, PyObject *args) {
    (void)self;
    Py_buffer key = {0};
    Py_buffer nonce = {0};
    Py_buffer aad = {0};
    Py_buffer plaintext = {0};
    const char *variant_name = NULL;
    Py_ssize_t variant_len = 0;
    PyObject *result = NULL;

    if (!PyArg_ParseTuple(args, "y*y*y*y*s#", &key, &nonce, &aad, &plaintext,
                          &variant_name, &variant_len)) {
        return NULL;
    }

    if (ensure_exact_length(&key, ASCON_KEY_BYTES, "key") != 0) {
        goto done;
    }
    if (ensure_min_length(&nonce, ASCON_NONCE_BYTES, "nonce") != 0) {
        goto done;
    }

    const struct ascon_variant *variant = resolve_variant(variant_name, variant_len);
    if (variant == NULL) {
        PyErr_SetString(PyExc_ValueError, "unknown Ascon variant");
        goto done;
    }

    uint64_t aad_len = 0;
    uint64_t msg_len = 0;
    if (convert_length(aad.len, &aad_len, "aad") != 0) {
        goto done;
    }
    if (convert_length(plaintext.len, &msg_len, "plaintext") != 0) {
        goto done;
    }

    if (plaintext.len > PY_SSIZE_T_MAX - ASCON_TAG_BYTES) {
        PyErr_SetString(PyExc_OverflowError, "ciphertext length exceeds platform limits");
        goto done;
    }

    Py_ssize_t out_len = plaintext.len + ASCON_TAG_BYTES;
    PyObject *out_obj = PyBytes_FromStringAndSize(NULL, out_len);
    if (out_obj == NULL) {
        goto done;
    }

    uint8_t *out_bytes = (uint8_t *)PyBytes_AS_STRING(out_obj);
    uint8_t *tag_ptr = out_bytes + plaintext.len;

    const uint8_t *key_ptr = (const uint8_t *)key.buf;
    const uint8_t *nonce_ptr = (const uint8_t *)nonce.buf;
    const uint8_t *aad_ptr = (const uint8_t *)aad.buf;
    const uint8_t *msg_ptr = (const uint8_t *)plaintext.buf;

    int rc = variant->encrypt_fn(tag_ptr, out_bytes, msg_ptr, msg_len, aad_ptr, aad_len,
                                 nonce_ptr, key_ptr);
    if (rc != 0) {
        Py_DECREF(out_obj);
        PyErr_SetString(PyExc_RuntimeError, "Ascon encryption failed");
        goto done;
    }

    result = out_obj;

done:
    release_buffers(&key, &nonce, &aad, &plaintext);
    return result;
}

static PyObject *native_decrypt(PyObject *self, PyObject *args) {
    (void)self;
    Py_buffer key = {0};
    Py_buffer nonce = {0};
    Py_buffer aad = {0};
    Py_buffer ciphertext = {0};
    const char *variant_name = NULL;
    Py_ssize_t variant_len = 0;
    PyObject *result = NULL;

    if (!PyArg_ParseTuple(args, "y*y*y*y*s#", &key, &nonce, &aad, &ciphertext,
                          &variant_name, &variant_len)) {
        return NULL;
    }

    if (ensure_exact_length(&key, ASCON_KEY_BYTES, "key") != 0) {
        goto done;
    }
    if (ensure_min_length(&nonce, ASCON_NONCE_BYTES, "nonce") != 0) {
        goto done;
    }

    if (ciphertext.len < ASCON_TAG_BYTES) {
        PyErr_SetString(PyExc_ValueError, "ciphertext too short");
        goto done;
    }

    const struct ascon_variant *variant = resolve_variant(variant_name, variant_len);
    if (variant == NULL) {
        PyErr_SetString(PyExc_ValueError, "unknown Ascon variant");
        goto done;
    }

    uint64_t aad_len = 0;
    uint64_t body_len = 0;
    Py_ssize_t plaintext_len = ciphertext.len - ASCON_TAG_BYTES;

    if (convert_length(aad.len, &aad_len, "aad") != 0) {
        goto done;
    }
    if (convert_length(plaintext_len, &body_len, "ciphertext") != 0) {
        goto done;
    }

    PyObject *out_obj = PyBytes_FromStringAndSize(NULL, plaintext_len);
    if (out_obj == NULL) {
        goto done;
    }

    uint8_t *out_bytes = (uint8_t *)PyBytes_AS_STRING(out_obj);
    const uint8_t *cipher_ptr = (const uint8_t *)ciphertext.buf;
    const uint8_t *tag_ptr = cipher_ptr + plaintext_len;
    const uint8_t *key_ptr = (const uint8_t *)key.buf;
    const uint8_t *nonce_ptr = (const uint8_t *)nonce.buf;
    const uint8_t *aad_ptr = (const uint8_t *)aad.buf;

    int rc = variant->decrypt_fn(out_bytes, tag_ptr, cipher_ptr, body_len, aad_ptr,
                                 aad_len, nonce_ptr, key_ptr);
    if (rc != 0) {
        Py_DECREF(out_obj);
        Py_INCREF(Py_None);
        result = Py_None;
        goto done;
    }

    result = out_obj;

done:
    release_buffers(&key, &nonce, &aad, &ciphertext);
    return result;
}

static PyMethodDef AsconMethods[] = {
    {"encrypt", native_encrypt, METH_VARARGS, "Encrypt using the native Ascon backend."},
    {"decrypt", native_decrypt, METH_VARARGS, "Decrypt using the native Ascon backend."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef asconmodule = {
    PyModuleDef_HEAD_INIT,
    "_ascon_native",
    "Native bindings for AEAD Ascon primitives.",
    -1,
    AsconMethods,
};

PyMODINIT_FUNC PyInit__ascon_native(void) {
    return PyModule_Create(&asconmodule);
}

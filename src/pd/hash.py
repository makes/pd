import hashlib

HASH_ALGO = "sha1"

FAST_HASH_SAMPLE_SIZE = 1024
FAST_HASH_N_SAMPLES = 512


def compute_file_hash(filepath):
    return _compute_fast_file_hash(filepath, HASH_ALGO)


def _compute_fast_file_hash(filepath, algorithm="sha1", n_samples=None, sample_size=None):
    if n_samples is None:
        n_samples = FAST_HASH_N_SAMPLES
    if sample_size is None:
        sample_size = FAST_HASH_SAMPLE_SIZE
    data = _sample_file(filepath, n_samples=FAST_HASH_N_SAMPLES, sample_size=FAST_HASH_SAMPLE_SIZE)
    return _compute_data_hash(data, algorithm)


# function to compute hash from binary data
def _compute_data_hash(data, algorithm="sha1"):
    hash = hashlib.new(algorithm)
    hash.update(data)
    return hash.hexdigest()


# Read n_blocks equidistant blocks of size block_size from file filepath.
# If file size is less than n*s+n, read entire file.
def _sample_file(filepath, n_samples, sample_size):
    if n_samples < 2:
        raise ValueError("n_samples must be at least 2")
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1")
    with open(filepath, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0)
        if file_size <= n_samples * sample_size:
            return f.read()
        offset = (file_size - sample_size) // (n_samples - 1)
        remainder = (file_size - sample_size) % (n_samples - 1)
        start_gap = remainder // 2 + remainder % 2
        end_gap = remainder // 2
        data = b""
        start = 0
        for i in range(n_samples):
            gap = 0
            if i == 1:
                gap = start_gap
            if i == n_samples - 1:
                gap += end_gap
            start += gap
            f.seek(start)
            data += f.read(sample_size)
            start += offset
        return data

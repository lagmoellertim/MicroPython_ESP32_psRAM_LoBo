import uos
import utime
from machine import I2S

#
#    Audio data recorder example
#    - reads audio sample data from I2S microphone
#    - writes sample data to SD Card as WAV file
#    - based on Adafruit I2S MEMS Microphone breakout board
#    - SPH0645LM4H-B device
#
#    For each audio sample the microphone transmits 8 bytes onto the I2S 'DIN' line
#    - 4 bytes for the Right channel followed by 4 bytes for the Left channel
#    - MSB byte first
#
#    Bytes on the DIN line shown below:
#
#    |              Right channel            |             Left channel              |
#    |  MSB-R  |  xxxxx  |  xxxxx  |  LSB-R  |  MSB-L  |  xxxxx  |  xxxxx  |  LSB-L  |
#    |  BYTE7  |  BYTE6  |  BYTE5  |  BYTE4  |  BYTE3  |  BYTE2  |  BYTE1  |  BYTE0  |
#
#    The Adafruit board has the SEL pin pulled Low.  This causes the SPH0645LM4H-B device
#    to transmit on the Left channel ONLY.  No sample data is transmitted on the Right channel
#
#    Refering to the above DIN behaviour, BYTE7->BYTE4 and BYTE0 will always be 0
#    Each audio sample for the SPH0645LM4H-B has 18 bits of resolution which appear on BYTE3->BYTE1:
#
#    |  0x00   |   0x00  |   0x00  |   0x00  |  BYTE3  |  BYTE2  |  BYTE1  |   0x00  |
#
#        BYTE3:  Sample bits 17:10
#        BYTE2:  Sample bits 9:2
#        BYTE1:  Sample bits 1:0 with lowest six bits 0
#
#    In the example code below, only the upper 16 bits of sample data is used (BYTE3 and BYTE2)
#    The 2 bits in BYTE1 are discarded.
#
#    For every 8 bytes of data transmitted by the microphone 2 bytes are written to the SD Card

# SD Card config

NUM_BYTES_IN_SDCARD_SECTOR = 512

# Microphone related config

SAMPLES_PER_SECOND = 10000
RECORD_TIME_IN_SECONDS = 10
NUM_BYTES_RX = 8
NUM_BYTES_USED = 2
BITS_PER_SAMPLE = NUM_BYTES_USED * 8
NUM_BYTES_IN_SAMPLE_BLOCK = NUM_BYTES_IN_SDCARD_SECTOR * (NUM_BYTES_RX
        // NUM_BYTES_USED)
NUM_SAMPLE_BYTES_IN_WAV = RECORD_TIME_IN_SECONDS * SAMPLES_PER_SECOND \
    * NUM_BYTES_USED


def gen_wav_header(
    sampleRate,
    bitsPerSample,
    channels,
    samples,
    ):
    datasize = samples * channels * bitsPerSample // 8
    o = bytes('RIFF', 'ascii')  # (4byte) Marks file as RIFF
    o += (datasize + 36).to_bytes(4, 'little')  # (4byte) File size in bytes excluding this and RIFF marker
    o += bytes('WAVE', 'ascii')  # (4byte) File type
    o += bytes('fmt ', 'ascii')  # (4byte) Format Chunk Marker
    o += (16).to_bytes(4, 'little')  # (4byte) Length of above format data
    o += (1).to_bytes(2, 'little')  # (2byte) Format type (1 - PCM)
    o += channels.to_bytes(2, 'little')  # (2byte)
    o += sampleRate.to_bytes(4, 'little')  # (4byte)
    o += (sampleRate * channels * bitsPerSample // 8).to_bytes(4,
            'little')  # (4byte)
    o += (channels * bitsPerSample // 8).to_bytes(2, 'little')  # (2byte)
    o += bitsPerSample.to_bytes(2, 'little')  # (2byte)
    o += bytes('data', 'ascii')  # (4byte) Data Chunk Marker
    o += datasize.to_bytes(4, 'little')  # (4byte) Data size in bytes
    return o


wav_header = gen_wav_header(SAMPLES_PER_SECOND, BITS_PER_SAMPLE, 1,
                            SAMPLES_PER_SECOND * RECORD_TIME_IN_SECONDS)
audio = I2S(  # dmacount: 2 to 128   dmalen 8 to 1024
    id=I2S.NUM0,
    sck=14,
    ws=15,
    sdin=32,
    mode=I2S.MASTER | I2S.RX,
    samplerate=SAMPLES_PER_SECOND,
    bits=I2S.BPS32,
    channelformat=I2S.RIGHT_LEFT,
    commformat=I2S.I2S | I2S.I2S_MSB,
    dmacount=128,
    dmalen=128,
    )
samples = bytearray(NUM_BYTES_IN_SAMPLE_BLOCK)
sd_sector = bytearray(NUM_BYTES_IN_SDCARD_SECTOR)
uos.sdconfig(
    uos.SDMODE_SPI,
    clk=18,
    mosi=23,
    miso=19,
    cs=4,
    maxspeed=40,
    )
uos.mountsd()
uos.statvfs('/sd')
with open('/sd/upy.wav', 'wb') as s:
    s.write(wav_header)
    for j in range(NUM_SAMPLE_BYTES_IN_WAV
                   // NUM_BYTES_IN_SDCARD_SECTOR):
        start = utime.ticks_us()
        numread = audio.readinto(samples)
        end = utime.ticks_us()

        # print("read mic (us) = ", end-start)

        start = utime.ticks_us()
        for i in range(NUM_BYTES_IN_SAMPLE_BLOCK // NUM_BYTES_RX):
            sd_sector[i * 2] = samples[i * 8 + 2]
            sd_sector[i * 2 + 1] = samples[i * 8 + 3]
        end = utime.ticks_us()
        print ('decimate (us) = ', end - start)
        start = utime.ticks_us()
        numwrite = s.write(sd_sector)
        end = utime.ticks_us()

        # print("write sdcard (us) = ", end-start)

audio.deinit()

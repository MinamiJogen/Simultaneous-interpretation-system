import ffmpeg

# ffmpeg.input('temp2.webm').output('out.webm',metadata="duration=00:00:07.000000000", map=0, c='copy').overwrite_output().run()


file1 = open("temp0.webm","rb")
file2 = open("temp1.webm","rb")
file3 = open("temp2.webm","rb")

# # buffer1 = file1.buffer.read()
# # buffer2 = file2.buffer.read()
# # buffer3 = file3.buffer.read()

barray1 = bytearray(file1.read())
barray2 = bytearray(file2.read())
barray3 = bytearray(file3.read())


for i in range(5000):
    barray3[i] = barray1[i]

file4 = open("out.webm","wb")
file4.write(bytes(barray3))


# ssarray = barray1[0:3000]
# file4 = open("head.bin","wb")
# file4.write(bytes(ssarray))

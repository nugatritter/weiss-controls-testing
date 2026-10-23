# Startskript der Test-SoftIOC
dbLoadRecords("/opt/softioc/test.db")
iocInit()
dbpf WEISS:TEST:WAVE "[0,1,4,9,16,25,36,49,64,81]"

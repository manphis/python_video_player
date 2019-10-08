import os.path
import glob
import cv2
from os import listdir
from argparse import ArgumentParser

rate = 0.00875
timestampList = []
MAX_INDEX = 16
IMAGE_FOLDER = "decode"

def getGyro(msb, lsb):
	value = (msb & 0xFF) << 8 | lsb
	if value > 32767:
		value = (65536 - value) * (-1)
	gyro = value * rate

	return gyro


def getAcc(msb, lsb):
	value = (msb & 0xFF) << 8 | lsb
	if value > 32767:
		value = (65536 - value) * (-1)

	acc = (value / 32768.0) * 2.0

	return acc


def readTimestamp(filePath):
	f = open(filePath)
	timestampList[:] = []
	line = f.readline()

	while line:
		timestampList.append(int(line.strip()))
		line = f.readline()
	f.close()


def createIMUAndTSFile(filePath):
	if not os.path.isfile(filePath):
		return

	line_bytes = 18
	samplerate = 90000
	start_rtp_timestamp = 0
	end_rtp_timestamp = 0
	imu_count = 0
	tsListIndex = 0
	total_ts_checked = 0
	total_imu_count = 0
	total_ts_count = 0
	imuList = []

	f = open(filePath, "rb")
	statinfo = os.stat(filePath)
	file_lines = (int)(statinfo.st_size/18);
	print("file lines = ", file_lines)

	output_str = filePath.replace(".txt", "_imu.csv")
	output_file = open(output_str, "w+")

	print("no. of video timestamp =", len(timestampList))

	byte = f.read(line_bytes)
	
	while byte:
		# if byte[0]=='T' and byte[1]=='I' and byte[2]=='M' and byte[3]=='E':
		if chr(byte[0])=='T' and chr(byte[1])=='I' and chr(byte[2])=='M' and chr(byte[3])=='E':
			tv_sec = (byte[7] & 0xFF) << 24 | (byte[6] & 0xFF) << 16 | (byte[5] & 0xFF) << 8 | (byte[4] & 0xFF)
			tv_usec = (byte[11] & 0xFF) << 24 | (byte[10] & 0xFF) << 16 | (byte[9] & 0xFF) << 8 | (byte[8] & 0xFF)

			timestamp = int((tv_sec * samplerate) % (256**4) + (tv_usec * (samplerate * 1.0e-6)))

			if start_rtp_timestamp == 0:
				start_rtp_timestamp = int((tv_sec * samplerate) % (256**4) + (tv_usec * (samplerate * 1.0e-6)));
			else:
				end_rtp_timestamp = int((tv_sec * samplerate) % (256**4) + (tv_usec * (samplerate * 1.0e-6)));

				imuTickTime = int((end_rtp_timestamp - start_rtp_timestamp) / imu_count)
				if tsListIndex < len(timestampList):
					ts = timestampList[tsListIndex]

					while ts < start_rtp_timestamp:
						tsListIndex += 1
						if tsListIndex >= len(timestampList):
							break

						ts = timestampList[tsListIndex]

					while (ts >= start_rtp_timestamp) and (ts <= end_rtp_timestamp):
						offset = int((ts - start_rtp_timestamp) / imuTickTime)
						imuList[offset][0] = ts
						total_ts_checked += 1

						tsListIndex += 1
						if tsListIndex >= len(timestampList):
							break
						ts = timestampList[tsListIndex];

				for i in range(len(imuList)):
					imuData = imuList[i]
					imu_str = str(imuData[0]) + ", " + imuData[1] + "\r\n"
					output_file.write(imu_str)

				start_rtp_timestamp = end_rtp_timestamp

			print("rtp timestamp = ", start_rtp_timestamp)

			total_imu_count += imu_count
			total_ts_count += 1
			imu_count = 0
			imuList[:] = []

		else:
			gyro0 = getGyro(byte[1], byte[0])
			gyro1 = getGyro(byte[3], byte[2])
			gyro2 = getGyro(byte[5], byte[4])
			acc0 = getAcc(byte[7], byte[6])
			acc1 = getAcc(byte[9], byte[8])
			acc2 = getAcc(byte[11], byte[10])

			imu_str = str(gyro0) + ", " + str(gyro1) + ", " + str(gyro2) + ", " + str(acc0) + ", " + str(acc1) + ", " + str(acc2)

			if imu_count == 0 and total_imu_count == 0:
				print("first imu data = " + imu_str)
			imu_count += 1

			imu_ts = (byte[13] & 0xFF) << 16 | (byte[12] & 0xFF) << 8 | (byte[15] & 0xFF)

			if imu_ts == 0 or imu_ts - last_imu_ts < 3:
				last_imu_ts = imu_ts;
			else:
				print("ERROR!!!!! IMU DATA TIMESTAMP ERROR!!! diff = ", (imu_ts - last_imu_ts))
				break;

			imuList.append([0, imu_str]);

		byte = f.read(line_bytes)

	f.close()
	output_file.close()

	if total_ts_checked == len(timestampList):
		print("timestamp check PASS ", total_ts_checked, ":", len(timestampList))
	else:
		print("timestamp check FAILED ", total_ts_checked, ":", len(timestampList))

	print("total imu count = ", str(total_imu_count),
		" total ts count = ", str(total_ts_count),
		" total data count = ", str(total_imu_count + total_ts_count))
	if (total_imu_count+total_ts_count) != file_lines:
		print("parsing not match !!! file lines = ", file_lines, ", total data count = ", str(total_imu_count+total_ts_count))


def batchParse(rootFolder):
	for folderIndex in range(1, MAX_INDEX+2):
		if folderIndex == MAX_INDEX + 1:
			areaFolder = rootFolder + "/Area_free"
		else:
			areaFolder = rootFolder + "/Area_" + str(folderIndex)

		if not os.path.exists(areaFolder):
			continue

		videoFile = getVideoFile(areaFolder)
		print(videoFile)
		if videoFile == None:
			print("no q8h mp4 file in", areaFolder)
			continue

		timestampFilePath = areaFolder + "/" + videoFile.replace(".mp4", ".ts")
		if not os.path.isfile(timestampFilePath):
			continue

		readTimestamp(timestampFilePath);

		imuFilePath = areaFolder + "/" + videoFile.replace(".mp4", ".txt")
		if not os.path.isfile(imuFilePath):
			continue

		createIMUAndTSFile(imuFilePath)

		if not os.path.exists(areaFolder + "/" + IMAGE_FOLDER):
			os.mkdir(areaFolder + "/" + IMAGE_FOLDER)
		extractAndSaveMp4(areaFolder, areaFolder + "/" + videoFile)

		print("\n\n")


def getVideoFile(folder):
	fileLists = listdir(folder)
	mp4File = []
	for f in fileLists:
		if ("q8h" in f) and f.endswith(".mp4"):
			mp4File.append(f)
	if mp4File == []:
		return None

	return max(mp4File)


def extractAndSaveMp4(rootFolder, file):
	print("extractAndSaveMp4", file)
	vidcap = cv2.VideoCapture(file)
	success, image = vidcap.read()
	count = 0
	success = True
	while success:
		frame_name = "frame_%d.jpg" % timestampList[count]
		frame_full_name = rootFolder + "/" + IMAGE_FOLDER + "/" + frame_name
		cv2.imwrite(frame_full_name, image)     # save frame as JPEG file
		success,image = vidcap.read()
		count += 1
	print("decode %d images" % count)


if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument("-i", "--input", help="imu file name", dest="inputFile", required=True)

	args = parser.parse_args()

	if os.path.isfile(args.inputFile):
		print("isfile")
	elif os.path.isdir(args.inputFile):
		folderIndex = 1
		batchParse(args.inputFile)
	else:
		print("no such file")


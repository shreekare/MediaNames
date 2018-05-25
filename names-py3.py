# This is a python-3 script to rename media files to include datatimes and also update the 
# date times of jpg image's EXIF data based on the datatimes present in the filenames

import os
import re
import sys
import piexif
from PIL import Image
import datetime
import argparse
doesNotHaveAnyDateTime, needsChangeTime, onlyFileNameDoesNotHaveDateTime, dateTimesDiffer, noDateForPicasa, nonJpgFiles, fileCount = {}, {}, {}, {}, {}, {}, 0
zeroTimeOffset = datetime.timedelta(seconds = 0)

def handle_video(args, file, dir, filedict):
  sys.stdout.flush()
  global doesNotHaveAnyDateTime, needsChangeTime, onlyFileNameDoesNotHaveDateTime, dateTimesDiffer, noDateForPicasa, fileCount

  path = os.path.join(dir,file) if dir else file
  if not os.path.isfile(path):
    print('%s does not exist' % path)
    sys.exit(0)

  fileCount += 1
  
  dateFromName = None
  
  match = re.match('\d{8}_\d{6}',file)
  if match:
    try:
      dateFromName = datetime.datetime.strptime(match.group(0), "%Y%m%d_%H%M%S")
    except ValueError:
      print("File '%s' does not have a valid date time in its name" % path)
      doesNotHaveValidTimeInName = True
    filedict[file] = 1
  else:
    #print('%s does not match required file naming convention' % path)
    doesNotHaveValidTimeInName = True

  if args.preserve_name:
    name_tail = re.match('^[\d_]*([^\.]*)',file).group(1)
    name_tail = re.match('([^\.]*?)(MVI|)[ \(\)\d_]*$',name_tail).group(1)
  
  extn = re.search('(\.\w+)$',file).group(1).lower()
  if extn == '.mod':
    extn = '.mpg'
    
  ftime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
  if ftime > datetime.datetime.fromtimestamp(os.path.getctime(path)):
    datetime.datetime.fromtimestamp(os.path.getctime(path))
  
  if dateFromName and dateFromName != ftime:
    print("File '%s' has a datetime but is different from the file modified time %s" % (path, ftime))
  elif not dateFromName or dateFromName != ftime:
    if not args.rename_files:
      print("Filename '%s' does not have the datetime" % path)
      incrDict(onlyFileNameDoesNotHaveDateTime, dir)
      return
    nameFromDate = ftime.strftime('%Y%m%d_%H%M%S')
    renameSuccess = False
    while not renameSuccess:
      renameSuccess = not args.apply
      while nameFromDate + extn in filedict:
        ftime += datetime.timedelta(seconds = 1)
        nameFromDate = ftime.strftime('%Y%m%d_%H%M%S')
      new_name = nameFromDate + ('_' + name_tail if args.preserve_name and name_tail else '') + extn
      filedict[new_name] = 1
      new_name = os.path.join(dir, new_name)
      print('Renaming: %s to %s%s' % (path, new_name, '(diff - '+str(abs(ftime-dateFromName))+')' if dateFromName else ''))
      if args.apply:
        try:
          os.rename(path, new_name)
          renameSuccess = True
        except WindowsError:
          pass
    
    
def handle_image(args, file, dir, filedict):
  sys.stdout.flush()
  global doesNotHaveAnyDateTime, needsChangeTime, onlyFileNameDoesNotHaveDateTime, dateTimesDiffer, noDateForPicasa, fileCount

  path = os.path.join(dir,file) if dir else file
  if not os.path.isfile(path):
    print('%s does not exist' % path)
    sys.exit(0)

  fileCount += 1

  # read the image exif data
  img = Image.open(path)
  exif = piexif.load(img.info['exif'])
  img.close()
  
  foundExifDate = False
  dateFromName = None
  timeOffset = zeroTimeOffset
  
  cameraModel = exifVal(exif, '0th', piexif.ImageIFD.Model)
  #exifVal(exif, '0th', piexif.ImageIFD.Make) # will get the camera make
  
  if not args.Camera or args.Camera == cameraModel:
    timeOffset = datetime.timedelta(days = args.Days, hours = args.Hours, minutes = args.minutes, seconds = args.seconds)
    
  if args.verbose and timeOffset != zeroTimeOffset:
    print("Applying time offset of %s to the file %s" % (timeOffset, file))

  doesNotHaveValidTimeInName, dateForPicasaFound = False, False
  
  match = re.match('\d{8}_\d{6}',file)
  if match:
    try:
      dateFromName = datetime.datetime.strptime(match.group(0), "%Y%m%d_%H%M%S")
    except ValueError:
      print("File '%s' does not have a valid date time in its name" % path)
      doesNotHaveValidTimeInName = True
    filedict[file] = 1
  else:
    print("File '%s' does not have a valid date time in its name" % path)
    doesNotHaveValidTimeInName = True
    
  if args.preserve_name:
    name_tail = re.match('^[\d_]*([^\.]*)',file).group(1)
    name_tail = re.match('([^\.]*?)(IMG|)[ \(\)\d_]*$',name_tail).group(1)

  exifDateStr = exifVal(exif, 'Exif', piexif.ExifIFD.DateTimeOriginal)
  if exifDateStr:
    dateForPicasaFound = True
  else:
    exifDateStr = exifVal(exif, 'Exif', piexif.ExifIFD.DateTimeDigitized)
    
  if not exifDateStr:
    exifDateStr = exifVal(exif, '0th', piexif.ImageIFD.DateTime)

  if exifDateStr:
    exifDateTime = datetime.datetime.strptime(exifDateStr, '%Y:%m:%d %H:%M:%S')
    foundExifDate = True
    
    exifDateTime += timeOffset
    nameFromDate = exifDateTime.strftime('%Y%m%d_%H%M%S')
    if (not args.only_incorrect or dateFromName is None) and not re.match('^'+nameFromDate, file):
      if args.change_time:
        if not dateFromName:
          print("Cannot change EXIF date for %s, since the filename is not a valid datetime" % path)
          return

        print("Changing EXIF date of %s (taken by %s) from %s to %s (diff - %s)" % (path, cameraModel, exifDateTime, dateFromName, abs(exifDateTime-dateFromName)))
        if args.apply:
          saveImageWithNewDate(path, dateFromName)
      elif args.rename_files:
        renameSuccess = False
        #print("trying to rename %s" % path)
        numRetries = 10
        timeChanged = False
        while not renameSuccess:
          renameSuccess = not args.apply
          while nameFromDate+'.jpg' in filedict:
            exifDateTime += datetime.timedelta(seconds = 1)
            nameFromDate = exifDateTime.strftime('%Y%m%d_%H%M%S')
            timeChanged = True

          new_name = nameFromDate + ('_' + name_tail if args.preserve_name and name_tail else '') + '.jpg'
          filedict[new_name] = 1
          new_name = os.path.join(dir, new_name)
          print('Renaming: %s to %s%s' % (path, new_name, '(diff - '+str(abs(exifDateTime-dateFromName))+')' if dateFromName else ''))
          if args.apply:
            try:
              if timeChanged:
                print('Changing time for: %s' % path)
                saveImageWithNewDate(path, exifDateTime)
              os.rename(path, new_name)
              renameSuccess = True
            except WindowsError:
              numRetries -= 1
              if numRetries == 0:
                print('**** Could not rename: %s to %s%s!! Check permissions of the file' % (path, new_name, '(diff - '+str(abs(exifDateTime-dateFromName))+')' if dateFromName else ''))
                renameSuccess = True
              pass
      elif dateFromName:
        if abs(exifDateTime-dateFromName) > datetime.timedelta(minutes = 1):
          print('%s: %s (%s) (by %s) - datetimes in filename and EXIF data differ' % (path, exifDateTime, abs(exifDateTime-dateFromName), cameraModel))
          incrDict(dateTimesDiffer, dir)
      else:
        print('%s: %s (%s) has to be renamed' % (path, exifDateTime, cameraModel))
    elif args.verbose:
      print('%s: is named appropriately' % path)

  if not dateForPicasaFound:
    #print('%s : does not have exif date' % path)
    if args.change_time:
      if not dateFromName:
        print("Cannot change EXIF date for %s, since the filename does not have valid datetime" % path)
      else:
        if args.apply:
          saveImageWithNewDate(path, dateFromName)
          print("Wrote EXIF date for %s as %s (by %s) to the file" % (path, dateFromName, cameraModel))
        else:
          print("Adding EXIF date for %s as %s (by %s)" % (path, dateFromName, cameraModel))
    else:
      if dateFromName and not foundExifDate:
        print("Filename '%s' has valid data time. Its EXIF has to be changed to include date" % path)
        incrDict(needsChangeTime, dir)
      if foundExifDate:
        print("File '%s' has a datetime in EXIF, but it does not have datetime that is needed for picasa" % path)
        incrDict(noDateForPicasa, dir)
    if doesNotHaveValidTimeInName:
      incrDict(doesNotHaveAnyDateTime, dir)
  elif doesNotHaveValidTimeInName:
    print("File '%s' has a datetime in EXIF, but filename does not have the datetime" % path)
    incrDict(onlyFileNameDoesNotHaveDateTime, dir)

def exifVal(exif, tag1, tag2):
  if tag1 in exif and tag2 in exif[tag1]:
    return exif[tag1][tag2].decode('utf-8')
  return None

def exifBytesWithNewDate(exif, date):
  exif['0th'][piexif.ImageIFD.DateTime] = date.strftime('%Y:%m:%d %H:%M:%S')
  exif['Exif'][piexif.ExifIFD.DateTimeOriginal] = date.strftime('%Y:%m:%d %H:%M:%S')
  exif['Exif'][piexif.ExifIFD.DateTimeDigitized] = date.strftime('%Y:%m:%d %H:%M:%S')
  return piexif.dump(exif)

def saveImageWithNewDate(path, date):
  img = Image.open(path)
  exif = piexif.load(img.info['exif'])
  img.save(path, 'jpeg', exif=exifBytesWithNewDate(exif, date), quality='keep')
  img.close()

def incrDict(dict, key):
  dict[key] = dict[key] + 1 if key in dict else 1
  
def printDict(dict, msg):
  if dict:
    print(msg % sum(dict.values()))
    print('  -', '\n  - '.join(['%3d in %s' % (dict[key], key) for key in sorted(dict.keys())]))

def isFileOfType(name, extns):
  for extn in extns:
    if file.endswith(extn):
      return True
  return False
    
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--directory', default='.', help='Directory to parse recursively')
parser.add_argument('-a', '--apply', action='store_true', help='Apply time changes to EXIF data or rename files only when this is option is set. Omitting this option is just a dry-run.')
parser.add_argument('-c', '--change_time', action='store_true', help='File names are correct, change EXIF datetime to match the filename')
parser.add_argument('-p', '--preserve_name', action='store_true', help='Preserve the file name. Append it to the end of the file name. Valid only if with -r option')
parser.add_argument('-r', '--rename_files', action='store_true', help='Rename the files using the EXIF datetime')
parser.add_argument('-f', '--file', help='One image file name')
parser.add_argument('-v', '--verbose', action='store_true', help='Verbose')
parser.add_argument('-D', '--Days', type=int, default=0, help='Days offset')
parser.add_argument('-H', '--Hours', type=int, default=0, help='Hours offset')
parser.add_argument('-m', '--minutes', type=int, default=0, help='Minutes offset')
parser.add_argument('-s', '--seconds', type=int, default=0, help='Seconds offset')
parser.add_argument('-C', '--Camera', help='Camera for which offset has to be applied')
parser.add_argument('-o', '--only_incorrect', action='store_true', help='Change only files that are not in correct format')
args = parser.parse_args()

if args.rename_files and args.change_time:
  print("Either 'rename_files' or 'change_time' should be selected, not both")
  sys.exit(0)

filedict = {}

if args.file:
  handle_image(args, os.path.basename(args.file), os.path.dirname(args.file), filedict)
  sys.exit(0)

for path,dirs,files in os.walk(args.directory):
  for file in files:
    if path.endswith('.picasaoriginals'):
      continue

    if isFileOfType(file, ['jpg', 'JPG', 'gif']):
      handle_image(args, file, path, filedict)
    elif isFileOfType(file, ['avi', 'AVI', 'MTS', 'mp4', 'MP4', 'MOD', 'MOV', '3gp', '3GP']):
      handle_video(args, file, path, filedict)
    elif file == 'Thumbs.db':
      try:
        os.remove(os.path.join(path, file))
      except WindowsError:
        pass
    elif file.endswith('.ini'):
      pass
    elif not file.startswith('.'):
      print('%s/%s is not a image/video file that the script can handle' % (path, file))
      incrDict(nonJpgFiles, path)
      
print("")
print("Summary:")
printDict(doesNotHaveAnyDateTime, "%s file(s) do not have datetime neither in filename nor in EXIF data. "
                        "Change filenames to include valid datetime and then run the tool with -c option.")
printDict(needsChangeTime, "%s file(s) have valid datetime in filenames without date in EXIF data. Use -c option to modify EXIF data.")
printDict(noDateForPicasa, '%s file(s) have some EXIF datetime, but it does not have the EXIF datetime that picasa needs. Use -c option to modify EXIF data.')
printDict(onlyFileNameDoesNotHaveDateTime, "%s filename(s) do not have valid datetime, but EXIF data has date in it. Use -r option to modify file names.")
printDict(dateTimesDiffer, "For %s file(s), datetime in filename and EXIF data differ in some files. "
                        "Use either -r or -c option to fix either filenames or EXIF dates respectively.")
printDict(nonJpgFiles, "%s file(s) are neither image/video files.")
if not(doesNotHaveAnyDateTime or needsChangeTime or noDateForPicasa or onlyFileNameDoesNotHaveDateTime or dateTimesDiffer):
  print("Congrats!! All %d files in directory '%s' are named appropriately." % (fileCount, args.directory))
else:
  print("Saw a total of %d files in directory '%s'." % (fileCount, args.directory))

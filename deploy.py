
import pexpect
import sys
import os
from optparse import OptionParser

parser = OptionParser()
parser.add_option("--git")
parser.add_option("--git_branch")
parser.add_option("--git_user")
parser.add_option("--git_password")
parser.add_option("--git_folder", default='')
parser.add_option("--sftp_user")
parser.add_option("--sftp_host")
parser.add_option("--sftp_path", default='/')
parser.add_option("--sftp_password")

(options, args) = parser.parse_args()

if len(options.git_folder) > 0 and options.git_folder[0] == '/':
	options.git_folder = options.git_folder[1:]

if len(options.git_folder) > 0 and options.git_folder[len(options.git_folder) - 1] == '/':
	options.git_folder = options.git_folder[:len(options.git_folder) - 1]

print "Cloning repository..."

rm = pexpect.spawn("rm -rf /tmp/repo")
rm.logfile = sys.stdout
rm.expect(pexpect.EOF)

git = pexpect.spawn("git clone " + options.git + " /tmp/repo", timeout=300)
git.logfile = sys.stdout

i = git.expect(['pass', 'remote:'])
if i == 0:
	git.expect(':')
	git.sendline(options.git_password)

git.expect(pexpect.EOF)

os.chdir("/tmp/repo")

if options.git_branch:
	print "Checking out branch..."
	git = pexpect.spawn("git checkout " + options.git_branch)
	git.logfile = sys.stdout
	git.expect(pexpect.EOF)

hash = pexpect.run("git --no-pager log --color=never --pretty=format:%H -n 1")

print ""
print "Top commit hash: " + hash
print ""
print "Mounting remote filesystem..."

umount = pexpect.spawn("fusermount -u /mnt/remote")
umount.logfile = sys.stdout
umount.expect(pexpect.EOF)

mount = pexpect.spawn("sshfs " + options.sftp_user + "@" + options.sftp_host + ":" + options.sftp_path + " /mnt/remote", timeout=3000)
mount.logfile = sys.stdout

while mount.expect(['passphrase', 'password']) == 0:
	mount.sendline('')

mount.expect(':')
mount.sendline(options.sftp_password)
mount.expect(pexpect.EOF)

try:
	f = open("/mnt/remote/.hash", "r")
	last = f.readline()
	f.close()
except:
	last = None

if last:
	print "Current commit on the server: " + last
	if last == hash:
		print "Server is up-to-date!"
		exit()
		
	print "Determining difference..."
	diff = pexpect.run("git --no-pager diff --name-status --oneline " + last + " " + hash)
	delete = []
	copy = []
	
	for file in diff.splitlines():
		(flag, path) = file.split('\t', 2)
		if options.git_folder <> '':
			if path.indexOf(options.git_folder + '/') != 2:
				continue
		if flag == 'M' or flag == 'C' or flag == 'R' or flag == 'A':
			copy.append(path)
		elif flag == 'D':
			delete.append(path)
		elif flag == 'U':
			print ''
			print 'ERROR! Unmerged conflict in ' + path
			exit()
	if len(copy) > 0:
		print ''
		print "The following files will be copied:"
		for file in copy:
			print "\t" + file
	if len(delete) > 0:
		print ''
		print "The following files will be DELETED:"
		for file in delete:
			print "\t" + file
	print "Type 'yes' to confirm:"
	response = sys.stdin.readline()
	if response.strip() == "yes":
		for file in delete:
			print pexpect.run('rm -v "/mnt/remote/' + file + '"')
		for file in copy:
			cp = pexpect.spawn('cp -v "/tmp/repo/' + file + '" "/mnt/remote/' + file + '"')
			cp.logfile = sys.stdout
			if cp.expect(['No such file or directory', pexpect.EOF]) == 0:
				cp.expect(pexpect.EOF)
				print "Creating directory " + file.rsplit("/", 1)[0]
				os.makedirs('/mnt/remote/' + file.rsplit("/", 1)[0])
				print pexpect.run('cp -v "/tmp/repo/' + file + '" "/mnt/remote/' + file + '"')
	else:
		print "See you later!"
		exit()
else:
	print "No previous deployment are found on this server"
	print "Type 'yes' to copy all source code:"
	response = sys.stdin.readline()
	if response.strip() == "yes":
		print "Copying everything..."
		cp = pexpect.spawn("bash -c 'cp -rvf \"/tmp/repo/" + options.git_folder + "/*\" /mnt/remote'", timeout=3000)
		cp.logfile = sys.stdout
		cp.expect(pexpect.EOF)
	else:
		print "See you later!"
		exit()

f = open("/mnt/remote/.hash", "w")
f.write(hash)
f.close()

print "The server is now on commit " + hash

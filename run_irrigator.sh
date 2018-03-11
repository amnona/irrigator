echo 'run_irrigator.sh' > /home/pi/logs/run_irrigator_out.txt 2> /home/pi/logs/run_irrigator_err.txt
source /home/pi/miniconda3/bin/activate irrigator >> /home/pi/logs/run_irrigator_out.txt 2>> /home/pi/logs/run_irrigator_err.txt
cd /home/pi/git/irrigator
./irrigator.py >> /home/pi/logs/run_irrigator_out.txt 2>> /home/pi/logs/run_irrigator_err.txt
echo 'finished' >> /home/pi/logs/run_irrigator_out.txt 2>> /home/pi/logs/run_irrigator_err.txt

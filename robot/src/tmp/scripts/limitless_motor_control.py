from buildhat import Motor 
import keyboard

motor_b = Motor('A')
motor_a = Motor('B')
motor_c = Motor('C')

while True:
    # vertical rotation
    if keyboard.is_pressed("w"):
        print("A-Position ", motor_a.get_aposition())
        motor_a.run_for_degrees(180)
    if keyboard.is_pressed("s"):
        print("A-Position ", motor_a.get_aposition())
        motor_a.run_for_degrees(-180)
    # endeffector
    if keyboard.is_pressed("up"):
        print("B-Position ", motor_b.get_aposition())
        motor_b.run_for_degrees(180)
    if keyboard.is_pressed("down"):
        print("B-Position ", motor_b.get_aposition())
        motor_b.run_for_degrees(-180)
    # horizontal rotation
    if keyboard.is_pressed("a"):
        print("C-Position ", motor_c.get_aposition())
        motor_c.run_for_degrees(180)
    if keyboard.is_pressed("d"):
        print("C-Position ", motor_c.get_aposition())
        motor_c.run_for_degrees(-180)

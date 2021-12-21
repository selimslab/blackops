


from dataclasses import dataclass, field


@dataclass
class A:
    a: int

@dataclass
class B:
    b: str 
    robot: A

    def get_a(self):
        return self.robot.a
     
        

a = A(5)

b = B(b="b", robot=a)

print(a.a, b.get_a())

a.a = 8

print(a.a, b.get_a())

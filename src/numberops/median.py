# import collections
# from decimal import Decimal
# from heapq import *


# class MedianFinder:
#     def __init__(self, max_size: int):
#         self.small = []  # the smaller half of the list, max heap (invert min-heap)
#         self.large = []  # the larger half of the list, min heap

#         self.sq = collections.deque(maxlen=max_size)
#         self.lq = collections.deque(maxlen=max_size)

#     def add_num(self, num):
#         if len(self.sq) == len(self.lq):
#             heappush(self.large, -heappushpop(self.small, -num))
#             self.lq.append(num)
#         else:
#             heappush(self.small, -heappushpop(self.large, num))
#             self.sq.append(num)

#     def get_median(self):
#         if len(self.small) == len(self.large):
#             return Decimal(str(self.large[0] - self.small[0])) / Decimal(2)
#         else:
#             return Decimal(str(self.large[0]))

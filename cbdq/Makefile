.PHONY: all copy check

all: copy

copy: gnuerror.in.yaml gnewline.py
	./gnewline.py $< | xsel -b

check: gnuerror.in.yaml gnewline.py
	./gnewline.py --verify $<

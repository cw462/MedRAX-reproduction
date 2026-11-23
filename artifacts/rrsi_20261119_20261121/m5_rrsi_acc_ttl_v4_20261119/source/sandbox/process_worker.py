"""The native worker entrypoint inside the restricted process rootfs."""

from worker import main


if __name__ == '__main__':
    main()

from util.io_util import *
from util.logger import logger

#Base class for buffers
class Buffer:
    def __init__(self, stride, size, buf, offset, name):
        self.stride = stride
        self.size = size
        self.buf = buf
        self.offset = offset
        self.name = name

    def read(f, name=''):
        stride = read_uint32(f)
        size = read_uint32(f)
        offset = f.tell()
        buf = f.read(stride*size)
        return Buffer(stride, size, buf, offset, name)

    def write(f, buffer):
        write_uint32(f, buffer.stride)
        write_uint32(f, buffer.size)
        f.write(buffer.buf)

    def print(self, padding=2):
        pad = ' '*padding
        logger.log(pad+'{} (offset: {})'.format(self.name, self.offset))
        _, stride, size = self.get_meta()
        logger.log(pad+'  stride: {}'.format(stride))
        logger.log(pad+'  size: {}'.format(size))

    def dump(file, buffer):
        with open(file, 'wb') as f:
            f.write(buffer.buf)

    def get_meta(self):
        return self.offset, self.stride, self.size

#Vertex buffer
class VertexBuffer(Buffer):
    def __init__(self, stride, size, buf, offset, name):
        self.vertex_num = size
        super().__init__( stride, size, buf, offset, name)

    def read(f, name=''):
        buf = Buffer.read(f, name=name)
        return VertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

#Psitions for static mesh
class PositionVertexBuffer(VertexBuffer):
    def read(f, name=''):
        stride = read_uint32(f)
        vertex_num = read_uint32(f)
        buf = Buffer.read(f, name=name)
        check(stride, buf.stride, f)
        check(vertex_num, buf.size, f)

        return PositionVertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, vb):
        write_uint32(f, vb.stride)
        write_uint32(f, vb.vertex_num)
        Buffer.write(f, vb)

    def parse(self):
        parsed = struct.unpack('<'+'f'*3*self.size, self.buf)
        position = [parsed[i*3:i*3+3] for i in range(self.size)]
        position = [[p/100 for p in pos] for pos in position]
        position = [[pos[0], pos[2], pos[1]] for pos in position]
        return position

#Normals and UV maps for static mesh
class StaticMeshVertexBuffer(VertexBuffer):
    def __init__(self, uv_num, use_float32, stride, size, buf, offset, name):
        self.uv_num = uv_num
        self.use_float32=use_float32
        super().__init__( stride, size, buf, offset, name)

    def read(f, name=''):
        one = read_uint16(f)
        check(one, 1, f)
        uv_num = read_uint32(f)
        stride = read_uint32(f)
        vertex_num = read_uint32(f)
        use_float32 = read_uint32(f)
        read_null(f)
        buf = Buffer.read(f, name=name)
        check(stride, buf.stride, f)
        check(vertex_num, buf.size, f)
        check(stride, 8+uv_num*4*(1+use_float32), f)
        return StaticMeshVertexBuffer(uv_num, use_float32, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, vb):
        write_uint16(f, 1)
        write_uint32(f, vb.uv_num)
        write_uint32(f, vb.stride)
        write_uint32(f, vb.vertex_num)
        write_uint32(f, vb.use_float32)
        write_null(f)
        Buffer.write(f, vb)

    def parse(self):
        uv_type = 'f'*self.use_float32+'e'*(not self.use_float32)
        parsed = struct.unpack('<'+('B'*8+uv_type*2*self.uv_num)*self.size, self.buf)
        stride = 8+2*self.uv_num
        normals = [parsed[i*stride:i*stride+8] for i in range(self.size)]
        normals = [[i*2/255-1 for i in n] for n in normals]
        normal = [[n[4], n[6], n[5]] for n in normals]
        tangent = [[n[0], n[2], n[1], n[3]] for n in normals]
        texcoords = []
        for j in range(self.uv_num):
            texcoord = [parsed[i*stride+8+j*2:i*stride+8+j*2+2] for i in range(self.size)]
            texcoords.append(texcoord)
        return normal, tangent, texcoords

#Vertex colors
class ColorVertexBuffer(VertexBuffer):
    def read(f, name=''):
        one = read_uint16(f)
        check(one, 1, f)
        read_const_uint32(f, 4)
        vertex_num  = read_uint32(f)
        buf = Buffer.read(f, name=name)
        check(vertex_num, buf.size, f)
        return ColorVertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, vb):
        write_uint16(f, 1)
        write_uint32(f, 4)
        write_uint32(f, vb.vertex_num)
        Buffer.write(f, vb)

#Normals, positions, and UV maps for skeletal mesh
class SkeletalMeshVertexBuffer(VertexBuffer):
    def __init__(self, uv_num, use_float32, scale, stride, size, buf, offset, name):
        self.uv_num = uv_num
        self.use_float32=use_float32
        self.scale = scale
        super().__init__(stride, size, buf, offset, name)

    def read(f, name=''):
        one = read_uint16(f)
        check(one, 1, f)
        uv_num=read_uint32(f)
        use_float32UV=read_uint32(f)
        scale=read_vec3_f32(f)
        check(scale, [1,1,1], 'SkeletalMeshVertexBuffer: MeshExtension is not (1.0, 1.0 ,1.0))')
        read_null_array(f, 3, 'SkeletalMeshVertexBuffer: MeshOrigin is not (0,0,0))')
        buf = Buffer.read(f, name=name)
        return SkeletalMeshVertexBuffer(uv_num, use_float32UV, scale, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, vb):
        write_uint16(f, 1)
        write_uint32(f, vb.uv_num)
        write_uint32(f, vb.use_float32)
        write_vec3_f32(f, vb.scale)
        write_null_array(f, 3)
        Buffer.write(f, vb)

    def parse(self):
        uv_type = 'f'*self.use_float32+'e'*(not self.use_float32)
        parsed = struct.unpack('<'+('B'*8+'fff'+uv_type*2*self.uv_num)*self.size, self.buf)
        stride = 11+2*self.uv_num
        normals = [parsed[i*stride:i*stride+8] for i in range(self.size)]
        normals = [[i*2/255-1 for i in n] for n in normals]
        normal = [[n[4], n[6], n[5]] for n in normals]
        tangent = [[n[0], n[2], n[1], n[3]] for n in normals]
        position = [parsed[i*stride+8:i*stride+11] for i in range(self.size)]
        position = [[p/100 for p in pos] for pos in position]
        position = [[pos[0], pos[2], pos[1]] for pos in position]
        texcoords = []
        for j in range(self.uv_num):
            texcoord = [parsed[i*stride+11+j*2:i*stride+11+j*2+2] for i in range(self.size)]
            texcoords.append(texcoord)
        return normal, tangent, position, texcoords

    def get_range(self):
        uv_type = 'f'*self.use_float32+'e'*(not self.use_float32)
        parsed = struct.unpack('<'+('B'*8+'fff'+uv_type*2*self.uv_num)*self.size, self.buf)
        stride = 11+2*self.uv_num
        position = [parsed[i*stride+8:i*stride+11] for i in range(self.size)]
        position = [[p/100 for p in pos] for pos in position]
        x = [pos[0] for pos in position]
        y = [pos[2] for pos in position]
        z = [pos[1] for pos in position]
        return [max(x)-min(x), max(y)-min(y), max(z)-min(z)]

    def import_gltf(self, normal, tangent, position, texcoords, uv_num):
        uv_type = 'f'*self.use_float32+'e'*(not self.use_float32)
        self.uv_num = uv_num
        self.stride = 20+(1+self.use_float32)*4*self.uv_num
        self.size = len(normal)
        self.vertex_num = self.size
        normal = [[n[0], n[2], n[1], 1] for n, t in zip(normal, tangent)]
        tangent = [[t[0], t[2], t[1], t[3]] for t in tangent]
        normal = [tan+nor for tan, nor in zip(tangent, normal)]
        normal = [[int((i+1)*255/2) for i in n] for n in normal]
        position = [[pos[0], pos[2], pos[1]] for pos in position]
        position = [[p*100 for p in pos] for pos in position]
        buf = [n+p for n, p in zip(normal, position)]
        for texcoord in texcoords:
            buf = [b+t for b,t in zip(buf, texcoord)]
        buf = flatten(buf)
        self.buf = struct.pack('<'+('B'*8+'fff'+uv_type*2*self.uv_num)*self.size, *buf)

def flatten(l):
    return [x for row in l for x in row]

#Skin weights for skeletal mesh
class SkinWeightVertexBuffer(VertexBuffer):
    def __init__(self, extra_bone_flag, stride, size, buf, offset, name):
        self.extra_bone_flag = extra_bone_flag
        super().__init__(stride, size, buf, offset, name)

    def read(f, name=''):
        one = read_uint16(f)
        check(one, 1, f)
        extra_bone_flag = read_uint32(f) #if stride is 16 or not
        vertex_num  = read_uint32(f)
        buf = Buffer.read(f, name=name)
        check(vertex_num, buf.size, f)
        check(extra_bone_flag, buf.stride==16, f)
        return SkinWeightVertexBuffer(extra_bone_flag, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, vb):
        write_uint16(f, 1)
        write_uint32(f, vb.extra_bone_flag)
        write_uint32(f, vb.vertex_num)
        Buffer.write(f, vb)

    def parse(self):
        parsed = struct.unpack('<'+'B'*len(self.buf), self.buf)
        joint = [parsed[i*self.stride:i*self.stride+4] for i in range(self.size)]
        weight = [parsed[i*self.stride+self.stride//2:i*self.stride+self.stride//2+4] for i in range(self.size)]

        if self.extra_bone_flag:
            joint2 = [parsed[i*self.stride+4:i*self.stride+8] for i in range(self.size)]
            weight2 = [parsed[i*self.stride+self.stride//2+4:i*self.stride+self.stride//2+8] for i in range(self.size)]
        else:
            joint2=None
            weight2=None
        return joint, weight, joint2, weight2

    def import_gltf(self, joint, weight, extra_bone_flag):
        self.size = len(joint)
        self.vertex_num = self.size
        self.extra_bone_flag = extra_bone_flag
        self.stride = 8*(1+self.extra_bone_flag)
        weight = [[int(i*255) for i in w] for w in weight]
        buf = [j+w for j, w in zip(joint, weight)]
        buf = flatten(buf)
        #buf = [int(i) for i in buf]
        self.buf = struct.pack('<'+'B'*self.size*self.stride, *buf)
        pass

#Index buffer for static mesh
class StaticIndexBuffer(Buffer):
    def __init__(self, uint32_flag, stride, size, ib, offset, name):
        self.uint32_flag=uint32_flag
        super().__init__(stride, size, ib, offset, name)

    def read(f, name=''):
        uint32_flag=read_uint32(f) #0: uint16 id, 1: uint32 id
        buf = Buffer.read(f, name=name)
        return StaticIndexBuffer(uint32_flag, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, ib):
        write_uint32(f, ib.uint32_flag)
        Buffer.write(f, ib)

    def get_meta(self):
        stride = 2+2*self.uint32_flag
        size = len(self.buf)//stride
        return self.offset, stride, size

    def parse(self):
        _, stride, size = self.get_meta()
        form = [None, None, 'H', None, 'I']
        indices = struct.unpack('<'+form[stride]*size, self.buf)
        return indices

#Index buffer for skeletal mesh
class SkeletalIndexBuffer(Buffer):
    def read(f, name=''):
        stride=read_uint8(f) #2: uint16 id, 4: uint32 id
        buf = Buffer.read(f, name=name)
        check(stride, buf.stride)
        return SkeletalIndexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, ib):
        write_uint8(f, ib.stride)
        Buffer.write(f, ib)

    def parse(self):
        form = [None, None, 'H', None, 'I']
        indices = struct.unpack('<'+form[self.stride]*self.size, self.buf)
        return indices

    def update(self, new_ids, stride):
        form = [None, None, 'H', None, 'I']
        self.size = len(new_ids)
        #new_ids = [new_ids[i*3:(i+1)*3] for i in range(self.size//3)]
        #new_ids = [[ids[0], ids[2], ids[1]] for ids in new_ids]
        #new_ids = flatten(new_ids)
        #print(len(new_ids))
        self.stride = stride
        self.buf = struct.pack('<'+form[self.stride]*self.size, *new_ids)

#KDI buffers
class KDIBuffer(Buffer):
    def read(f, name=''):
        one = read_uint16(f)
        check(one, 1, f)
        buf = Buffer.read(f, name=name)
        return KDIBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(f, vb):
        write_uint16(f, 1)
        Buffer.write(f, vb)

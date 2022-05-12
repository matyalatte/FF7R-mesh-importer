from util.io_util import *
from util.logger import logger

from asset.lod_section import StaticLODSection, SkeletalLODSection
from asset.buffer import *

#Base class for LOD
class LOD:
    def __init__(self, vb, vb2, ib, ib2, color_vb=None):
        self.vb = vb
        self.vb2 = vb2
        self.ib = ib
        self.ib2 = ib2
        self.color_vb = color_vb

    def import_LOD(self, lod, name=''):
        #if len(self.sections)<len(lod.sections):
        #    raise RuntimeError('too many materials')
        f_num1=self.ib.size//3
        f_num2=lod.ib.size//3
        v_num1=self.vb.vertex_num
        v_num2=lod.vb.vertex_num
        uv_num1 = self.uv_num
        uv_num2 = lod.uv_num
        self.ib = lod.ib
        self.vb = lod.vb
        self.vb2 = lod.vb2
        self.ib2 = lod.ib2
        if self.color_vb is not None:
            self.color_vb = lod.color_vb
            if lod.color_vb is None:
                logger.log('Warning: The original mesh has color VB. But your mesh doesn\'t. I don\'t know if the injection works.')
        self.uv_num = lod.uv_num
        logger.log('LOD{} has been imported.'.format(name))
        logger.log('  faces: {} -> {}'.format(f_num1, f_num2))
        logger.log('  vertices: {} -> {}'.format(v_num1, v_num2))
        logger.log('  uv maps: {} -> {}'.format(uv_num1, uv_num2))

    #get all buffers LOD has
    def get_buffers(self):
        buffers = [self.vb, self.vb2, self.ib, self.ib2]
        if self.color_vb is not None:
            buffers += [self.color_vb]
        return buffers

    #reorder material ids
    def update_material_ids(self, new_material_ids):
        for section in self.sections:
            section.update_material_ids(new_material_ids)

    def get_meta_for_gltf(self):
        material_ids = [section.material_id for section in self.sections]
        return material_ids, self.uv_num

def split_list(l, first_ids):
    last_ids = first_ids[1:]+[len(l)]
    splitted = [l[first:last] for first, last in zip(first_ids, last_ids)]
    return splitted

#LOD for static mesh
class StaticLOD(LOD):
    def __init__(self, offset, sections, flags, vb, vb2, color_vb, ib, ib2, unk):
        self.offset = offset
        self.sections = sections
        self.flags = flags
        self.uv_num = vb2.uv_num
        super().__init__(vb, vb2, ib, ib2, color_vb=color_vb)
        self.unk = unk
        self.face_num=0
        for section in self.sections:
            self.face_num+=section.face_num

    def read(f):
        offset = f.tell()
        one = read_uint16(f) #strip flags
        check(one, 1, f)
        sections = read_array(f, StaticLODSection.read)

        flags = f.read(4)

        vb = PositionVertexBuffer.read(f, name='VB0') #xyz
        vb2 = StaticMeshVertexBuffer.read(f, name='VB2') #normals+uv_maps

        one = read_uint32(f)
        if one!=1: #color vertex buffer
            f.seek(-4, 1)
            color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        else:
            color_vb = None
            null=f.read(6)
            check(null, b'\x00'*6, f)

        ib = StaticIndexBuffer.read(f, name='IB')
        read_null(f)
        read_const_uint32(f, 1)
        null = read_uint32(f)
        if null!=0:
            raise RuntimeError('Unsupported index buffer detected. You can not import "Adjacency Buffer" and "Reversed Index Buffer".')

        ib2 = StaticIndexBuffer.read(f, name='IB2')
        unk = f.read(48)
        return StaticLOD(offset, sections, flags, vb, vb2, color_vb, ib, ib2, unk)

    def write(f, lod):
        write_uint16(f, 1)
        write_array(f, lod.sections, StaticLODSection.write, with_length=True)
        f.write(lod.flags)
        PositionVertexBuffer.write(f, lod.vb)
        StaticMeshVertexBuffer.write(f, lod.vb2)

        if lod.color_vb is not None:
            ColorVertexBuffer.write(f, lod.color_vb)
        else:
            write_uint32(f, 1)
            f.write(b'\x00'*6)

        StaticIndexBuffer.write(f, lod.ib)
        write_uint32_array(f, [0, 1, 0])
        StaticIndexBuffer.write(f, lod.ib2)
        f.write(lod.unk)

    def print(self, i, padding=0):
        pad=' '*padding
        logger.log(pad+'LOD{} (offset: {})'.format(i, self.offset))
        for j in range(len(self.sections)):
            self.sections[j].print(j, padding=padding+2)
        logger.log(pad+'  face_num: {}'.format(self.face_num))
        logger.log(pad+'  vertex_num: {}'.format(self.vb.vertex_num))
        logger.log(pad+'  uv_num: {}'.format(self.uv_num))
        for buf in self.get_buffers():
            buf.print(padding=padding+2)

    def import_LOD(self, lod, name=''):
        super().import_LOD(lod, name=name)
        self.sections=self.sections[:len(lod.sections)]
        if len(self.sections)<len(lod.sections):
            self.sections += [self.sections[-1].copy() for i in range(len(lod.sections)-len(self.sections))]
        for self_section, lod_section in zip(self.sections, lod.sections):
            self_section.import_section(lod_section)
        self.face_num = lod.face_num
        self.flags = lod.flags
        #self.unk = new_lod.unk #if import this, umodel will crash

    def parse_buffers_for_gltf(self):
        pos = self.vb.parse()
        normal, tangent, texcoords = self.vb2.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]

        ls = [normal, tangent, pos]
        normals, tangents, positions = [split_list(l, first_vertex_ids) for l in ls]

        texcoords = [split_list(l, first_vertex_ids) for l in texcoords]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i-first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        
        return normals, tangents, positions, texcoords, indices

#LOD for skeletal mesh
class SkeletalLOD(LOD):
    #sections: mesh data is separeted into some sections.
    #              each section has material id and vertex group.
    #active_bone_ids: maybe bone ids. but I don't know how it works.
    #bone_ids: active bone ids?
    #uv_num: the number of uv maps

    def __init__(self, f, ff7r=True):
        self.offset=f.tell()
        one = read_uint16(f)
        check(one, 1, f, 'Parse failed! (LOD:one)')
        self.sections=[SkeletalLODSection.read(f, ff7r=ff7r) for i in range(read_uint32(f))]

        self.KDI_buffer_size=0
        for section in self.sections:
            if section.unk2 is not None:
                self.KDI_buffer_size+=len(section.unk2)//16
        
        self.ib = SkeletalIndexBuffer.read(f, name='IB')

        num=read_uint32(f)
        self.active_bone_ids=f.read(num*2)

        read_null(f, 'Parse failed! (LOD:null1)')

        vertex_num=read_uint32(f)

        num=read_uint32(f)
        self.required_bone_ids=f.read(num*2)
        
        i=read_uint32(f)
        if i==0:
            self.null8=True
            read_null(f, 'Parse failed! (LOD:null2)')
        else:
            self.null8=False
            f.seek(-4,1)

        chk=read_uint32(f)
        if chk==vertex_num:
            self.unk_ids=read_uint32_array(f, len=vertex_num+1)
        else:
            self.unk_ids=None
            f.seek(-4,1)

        self.uv_num=read_uint32(f)
        self.vb = SkeletalMeshVertexBuffer.read(f, name='VB0')
        check(self.uv_num, self.vb.uv_num)
        self.vb2 = SkinWeightVertexBuffer.read(f, name='VB2')

        u=read_uint8(f)
        f.seek(-1,1)
        if u==1:#HasVertexColors
            self.color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        else:
            self.color_vb=None

        self.ib2 = SkeletalIndexBuffer.read(f, name='IB2')

        if self.KDI_buffer_size>0:
            self.KDI_buffer=KDIBuffer.read(f, name='KDI_buffer')
            check(self.KDI_buffer.size, self.KDI_buffer_size, f)
            self.KDI_VB=KDIBuffer.read(f, name='KDI_VB')

    def read(f, ff7r):
        return SkeletalLOD(f, ff7r=ff7r)
    
    def write(f, lod):
        write_uint16(f, 1)
        write_array(f, lod.sections, SkeletalLODSection.write, with_length=True)
        SkeletalIndexBuffer.write(f, lod.ib)
        write_uint32(f, len(lod.active_bone_ids)//2)
        f.write(lod.active_bone_ids)
        write_null(f)
        write_uint32(f, lod.vb.vertex_num)
        write_uint32(f, len(lod.required_bone_ids)//2)
        f.write(lod.required_bone_ids)
        
        if lod.null8:
            write_null(f)
            write_null(f)
        if lod.unk_ids is not None:
            write_uint32(f, lod.vb.vertex_num)
            write_uint32_array(f, lod.unk_ids)
        write_uint32(f, lod.uv_num)
        SkeletalMeshVertexBuffer.write(f, lod.vb)
        SkinWeightVertexBuffer.write(f, lod.vb2)

        if lod.color_vb is not None:
            ColorVertexBuffer.write(f, lod.color_vb)

        SkeletalIndexBuffer.write(f, lod.ib2)

        if lod.KDI_buffer_size>0:
            KDIBuffer.write(f, lod.KDI_buffer)
            KDIBuffer.write(f, lod.KDI_VB)

    def import_LOD(self, lod, name=''):
        
        super().import_LOD(lod, name=name)
        self.sections=self.sections[:len(lod.sections)]
        if len(self.sections)<len(lod.sections):
            self.sections += [self.sections[-1].copy() for i in range(len(lod.sections)-len(self.sections))]
        for self_section, lod_section in zip(self.sections, lod.sections):
            self_section.import_section(lod_section)
        
        self.active_bone_ids=lod.active_bone_ids
        self.required_bone_ids=lod.required_bone_ids
        if self.KDI_buffer_size>0:
            if self.vb.vertex_num>=self.KDI_VB.size:
                self.KDI_VB.buf=self.KDI_VB.buf[:self.vb.vertex_num*16]
            else:
                self.KDI_VB.buf=b''.join([self.KDI_VB.buf, b'\xff'*4*(self.vb.vertex_num-self.KDI_VB.size)])
            self.KDI_VB.size=self.vb.size

    def get_buffers(self):
        buffers = super().get_buffers()
        if self.KDI_buffer_size>0:
            buffers += [self.KDI_buffer, self.KDI_VB]
        return buffers

    def print(self, name, bones, padding=0):
        pad=' '*padding
        logger.log(pad+'LOD '+name+' (offset: {})'.format(self.offset))
        for i in range(len(self.sections)):
            self.sections[i].print(str(i),bones, padding=padding+2)
        pad+=' '*2
        logger.log(pad+'  face num: {}'.format(self.ib.size//3))
        logger.log(pad+'  vertex num: {}'.format(self.vb.vertex_num))
        logger.log(pad+'  uv num: {}'.format(self.uv_num))
        for buf in self.get_buffers():
            buf.print(padding=padding+2)

    def remove_KDI(self):
        self.KDI_buffer_size=0
        self.KDI_buffer=None
        self.KDI_VB=None
        for section in self.sections:
            section.remove_KDI()

    def parse_buffers_for_gltf(self):
        normal, tangent, pos, texcoords = self.vb.parse()
        joint, weight, joint2, weight2 = self.vb2.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]
        vertex_groups = [section.vertex_group for section in self.sections]

        ls = [normal, tangent, pos, joint, weight]
        normals, tangents, positions, joints, weights = [split_list(l, first_vertex_ids) for l in ls]

        texcoords = [split_list(l, first_vertex_ids) for l in texcoords]

        def func(vertex_groups, joints, weights):
            return [[[vg[j[i]]*(w[i]!=0) for i in range(4)] for j, w in zip(joint, weight)] for joint, weight, vg in zip(joints, weights, vertex_groups)]

        joints = func(vertex_groups, joints, weights)
        
        if joint2 is not None:
            ls = [joint2, weight2]
            joints2, weights2 = [split_list(l, first_vertex_ids) for l in ls]
            joints2 = func(vertex_groups, joints2, weights2)
        else:
            joints2, weights2 = None, None

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i-first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        
        return normals, tangents, positions, texcoords, joints, weights, joints2, weights2, indices

    def gen_adjacency(self):
        ib = list(self.ib.parse())
        faces = [ib[i*3:(i+1)*3] for i in range(len(ib)//3)]
        adjacency = [f+[f[0],f[1],f[1],f[2],f[2],f[0]]+f for f in faces]
        adjacency = [x for row in adjacency for x in row]
        self.ib2.update(adjacency)